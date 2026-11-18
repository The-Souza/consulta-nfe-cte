import threading

import pytest

import api
from ui.workers.search import BRAKE_SECONDS, SearchCallbacks, SearchWorker
from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK, Tone, search_tone

OK = ("123", SEARCH_OK, "Sim")
NO_CTE = ("-", SEARCH_NO_CTE, "Não")
NOT_FOUND = ("-", SEARCH_NOT_FOUND, "-")


def failed():
    return api.ConnectionFailed("down")


class FakeInvoices:
    """get_invoice that plays a scripted list of results per NF-e; exceptions are raised."""

    def __init__(self, script: dict[int, list]):
        self._script = {n: list(results) for n, results in script.items()}
        self.calls: list[int] = []

    def __call__(self, session, invoice_num, stop=None):
        self.calls.append(invoice_num)
        result = self._script[invoice_num].pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class Run:
    """Runs a SearchWorker synchronously (no thread, no Tk) and records what it reports."""

    def __init__(self, script, *, relogin=lambda: None, stop=None, wait=None, warm_up=None):
        self.events: list[tuple] = []
        self.rows: list[dict] = []
        self.waits: list[float] = []
        self.warmed: list[int] = []
        self.get_invoice = FakeInvoices(script)
        callbacks = SearchCallbacks(
            on_row=self._on_row,
            on_notice=lambda text: self.events.append(("notice", text)),
            on_done=lambda failures: self.events.append(("done", failures)),
            on_cancel=lambda: self.events.append(("cancel",)),
            on_session_lost=lambda: self.events.append(("lost",)),
        )
        SearchWorker(
            session=None,
            invoices=list(script),
            stop_event=stop or threading.Event(),
            after_fn=lambda _delay, fn, *args: fn(*args),
            callbacks=callbacks,
            relogin=relogin,
            get_invoice=self.get_invoice,
            warm_up=warm_up or (lambda session, n: self.warmed.append(n)),
            wait=wait or self.waits.append,
            pace=0,
        ).run()

    def _on_row(self, row, prog, current, total, elapsed):
        self.rows.append(row)
        self.events.append(("row", row["NF-e"], row["Status"]))

    def notices(self) -> list[str]:
        return [e[1] for e in self.events if e[0] == "notice"]

    @property
    def last(self) -> tuple:
        return self.events[-1]


# happy path and second pass --------------------------------------------------------

def test_all_found_finishes_without_failures():
    run = Run({1: [OK], 2: [NO_CTE]})

    assert run.events == [("row", 1, SEARCH_OK), ("row", 2, SEARCH_NO_CTE), ("done", [])]
    assert run.waits == []
    assert run.warmed == [1]


def test_second_pass_retries_connection_failures_and_updates_rows():
    run = Run({1: [failed(), OK], 2: [OK]})

    assert run.get_invoice.calls == [1, 2, 1]
    assert run.events[:2] == [("row", 1, CONNECTION_FAILED), ("row", 2, SEARCH_OK)]
    assert run.events[-2:] == [("row", 1, SEARCH_OK), ("done", [])]
    assert len(run.notices()) == 1


def test_persistent_failure_is_reported_as_connection_failure():
    run = Run({1: [failed(), failed()]})

    assert run.last == ("done", [1])
    assert run.rows[-1]["Status"] == CONNECTION_FAILED
    assert search_tone(run.rows[-1]["Status"]) is Tone.CONNECTION


def test_not_found_and_no_cte_are_not_retried():
    run = Run({1: [NOT_FOUND], 2: [NO_CTE]})

    assert run.get_invoice.calls == [1, 2]
    assert run.last == ("done", [])


def test_other_errors_show_the_message_and_are_not_retried():
    run = Run({1: [ValueError("Resposta inesperada")]})

    assert run.get_invoice.calls == [1]
    assert run.rows[0]["Status"] == "Resposta inesperada"
    assert run.last == ("done", [])


def test_row_keeps_cte_and_image():
    run = Run({1: [OK]})

    assert run.rows[0] == {"NF-e": 1, "CT-e": "123", "Imagem": "Sim", "Status": SEARCH_OK}


# brake ----------------------------------------------------------------------------

def test_three_failures_in_a_row_pause_once():
    run = Run({1: [failed(), OK], 2: [failed(), OK], 3: [failed(), OK], 4: [OK]})

    assert run.waits == [BRAKE_SECONDS]
    assert run.notices()[0] == "Servidor instável, aguardando…"
    assert run.last == ("done", [])


def test_a_success_resets_the_brake_count():
    run = Run({1: [failed(), OK], 2: [failed(), OK], 3: [OK], 4: [failed(), OK]})

    assert run.waits == []


def test_brake_also_applies_in_the_second_pass():
    run = Run({n: [failed(), failed()] for n in (1, 2, 3)})

    assert run.waits == [BRAKE_SECONDS, BRAKE_SECONDS]
    assert run.last == ("done", [1, 2, 3])


# session --------------------------------------------------------------------------

def test_expired_session_logs_in_again_and_continues():
    relogins = []

    run = Run({1: [api.SessionExpired("401"), OK]}, relogin=lambda: relogins.append(1))

    assert relogins == [1]
    assert run.events == [("row", 1, SEARCH_OK), ("done", [])]


def test_failed_relogin_stops_the_search():
    def failing_login():
        raise ValueError("E-mail ou senha inválidos.")

    run = Run({1: [OK], 2: [api.SessionExpired("401")], 3: [OK]}, relogin=failing_login)

    assert run.events == [("row", 1, SEARCH_OK), ("lost",)]
    assert run.get_invoice.calls == [1, 2]


# cancel ---------------------------------------------------------------------------

def test_stop_before_an_invoice_cancels():
    stop = threading.Event()
    stop.set()

    run = Run({1: [OK]}, stop=stop)

    assert run.events == [("cancel",)]


def test_cancel_during_a_retry_wait_cancels():
    run = Run({1: [api.Cancelled()], 2: [OK]})

    assert run.events == [("cancel",)]


def test_cancel_during_the_brake_cancels():
    def cancelled_wait(seconds):
        raise api.Cancelled()

    run = Run({n: [failed()] for n in (1, 2, 3, 4)}, wait=cancelled_wait)

    assert run.last == ("cancel",)
    assert run.get_invoice.calls == [1, 2, 3]


# warm-up --------------------------------------------------------------------------

def test_failing_warm_up_does_not_stop_the_search():
    def failing_warm_up(session, invoice_num):
        raise RuntimeError("unexpected")

    run = Run({1: [OK]}, warm_up=failing_warm_up)

    assert run.events == [("row", 1, SEARCH_OK), ("done", [])]


@pytest.mark.parametrize("script", [{}])
def test_empty_list_finishes_without_calls(script):
    run = Run(script)

    assert run.events == [("done", [])]
    assert run.warmed == []
