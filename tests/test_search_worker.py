import threading
from datetime import date

import pytest

import api
from drivers import Delivery, DriverLookup
from ui.workers.search import BRAKE_SECONDS, SearchCallbacks, SearchWorker
from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK, Tone, search_tone

OK = ("123", SEARCH_OK, "Sim")
NO_CTE = ("-", SEARCH_NO_CTE, "Não")
NOT_FOUND = ("-", SEARCH_NOT_FOUND, "-")
OFF = DriverLookup({}, None, "off")


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

    def __init__(
        self, script, *, relogin=lambda: None, stop=None, wait=None, warm_up=None,
        drivers=None, lookup=OFF, by_cte=None,
    ):
        self.events: list[tuple] = []
        self.rows: list[dict] = []
        self.waits: list[float] = []
        self.warmed: list[int] = []
        self.driver_reads: list[tuple[list[int], int]] = []  # invoices read, invoices queried before it
        self.drivers_seen: list[DriverLookup] = []
        self.get_invoice = FakeInvoices(script)

        self.cte_reads: list[set[int]] = []

        def get_drivers(invoices):
            self.driver_reads.append((list(invoices), len(self.get_invoice.calls)))
            return lookup

        def get_drivers_by_cte(ctes):
            self.cte_reads.append(set(ctes))
            return by_cte or DriverLookup({}, None, "ok")

        callbacks = SearchCallbacks(
            on_row=self._on_row,
            on_notice=lambda text: self.events.append(("notice", text)),
            on_done=lambda failures: self.events.append(("done", failures)),
            on_cancel=lambda: self.events.append(("cancel",)),
            on_session_lost=lambda: self.events.append(("lost",)),
            on_drivers=self.drivers_seen.append,
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
            drivers=drivers,
            get_drivers=get_drivers,
            get_drivers_by_cte=get_drivers_by_cte,
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

    assert run.rows[0] == {
        "NF-e": 1, "CT-e": "123", "Imagem": "Sim", "Status": SEARCH_OK, "Motorista": "", "Entrega": None,
    }


# drivers --------------------------------------------------------------------------

LOOKUP = DriverLookup({1: Delivery("Ana", date(2026, 11, 12)), 2: Delivery("Bia", None)}, None, "ok")


def test_drivers_are_read_once_before_the_first_invoice():
    run = Run({1: [OK], 2: [OK]}, lookup=LOOKUP)

    assert run.driver_reads == [([1, 2], 0)]
    assert run.drivers_seen == [LOOKUP]


def test_rows_carry_driver_and_delivery_date():
    run = Run({1: [OK], 2: [NO_CTE], 3: [NOT_FOUND]}, lookup=LOOKUP)

    assert [(r["Motorista"], r["Entrega"]) for r in run.rows] == [
        ("Ana", date(2026, 11, 12)), ("Bia", None), ("", None),
    ]


def test_connection_failure_rows_also_carry_the_driver():
    run = Run({1: [failed(), failed()]}, lookup=LOOKUP)

    assert all(r["Motorista"] == "Ana" for r in run.rows)


def test_a_lookup_already_read_is_reused():
    run = Run({1: [OK]}, drivers=LOOKUP)

    assert run.driver_reads == []
    assert run.drivers_seen == []
    assert run.rows[0]["Motorista"] == "Ana"


def test_failed_lookup_does_not_stop_the_search():
    failed_lookup = DriverLookup({}, None, "failed")

    run = Run({1: [OK]}, lookup=failed_lookup)

    assert run.drivers_seen == [failed_lookup]
    assert run.events == [("row", 1, SEARCH_OK), ("done", [])]
    assert run.rows[0]["Motorista"] == ""


# drivers by CT-e (load issued with a single XML) ------------------------------------

LOAD = ("25440", SEARCH_OK, "Não")
EMPTY = DriverLookup({}, None, "ok")
BY_CTE = DriverLookup({25440: Delivery("Paulo", date(2026, 10, 21))}, None, "ok")


def test_invoices_without_driver_are_looked_up_by_cte_at_the_end():
    run = Run({1: [OK], 5: [LOAD], 6: [LOAD]}, lookup=LOOKUP, by_cte=BY_CTE)

    assert run.cte_reads == [{25440}]
    assert run.events[-3:] == [("row", 5, SEARCH_OK), ("row", 6, SEARCH_OK), ("done", [])]
    assert [(r["NF-e"], r["Motorista"], r["Entrega"]) for r in run.rows[-2:]] == [
        (5, "Paulo", date(2026, 10, 21)), (6, "Paulo", date(2026, 10, 21)),
    ]


def test_the_merged_lookup_is_reported_again():
    run = Run({1: [OK], 5: [LOAD]}, lookup=LOOKUP, by_cte=BY_CTE)

    merged = run.drivers_seen[-1]
    assert merged.deliveries[5] == Delivery("Paulo", date(2026, 10, 21))
    assert merged.deliveries[1] == LOOKUP.deliveries[1]
    assert len(run.drivers_seen) == 2


def test_only_rows_without_driver_and_with_cte_are_looked_up():
    run = Run({1: [OK], 3: [NOT_FOUND], 4: [failed(), failed()], 5: [LOAD]}, lookup=LOOKUP, by_cte=BY_CTE)

    assert run.cte_reads == [{25440}]


def test_cte_not_found_leaves_the_row_untouched():
    run = Run({5: [LOAD]}, lookup=EMPTY, by_cte=EMPTY)

    assert run.cte_reads == [{25440}]
    assert run.events == [("row", 5, SEARCH_OK), ("done", [])]
    assert run.drivers_seen == [EMPTY]


def test_nothing_pending_makes_no_cte_read():
    run = Run({1: [OK], 2: [NO_CTE]}, lookup=LOOKUP)

    assert run.cte_reads == []


@pytest.mark.parametrize("state", ["off", "failed"])
def test_no_cte_read_when_supabase_is_off_or_failed(state):
    run = Run({5: [LOAD]}, lookup=DriverLookup({}, None, state))

    assert run.cte_reads == []


def test_retry_reuses_drivers_found_by_cte():
    merged = DriverLookup({5: Delivery("Paulo", date(2026, 10, 21))}, None, "ok")

    run = Run({5: [LOAD]}, drivers=merged)

    assert run.cte_reads == []
    assert run.rows[0]["Motorista"] == "Paulo"


def test_cancel_before_the_search_still_reports_the_lookup():
    stop = threading.Event()
    stop.set()

    run = Run({1: [OK]}, stop=stop, lookup=LOOKUP)

    assert run.drivers_seen == [LOOKUP]
    assert run.events == [("cancel",)]


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
    assert run.driver_reads == []
