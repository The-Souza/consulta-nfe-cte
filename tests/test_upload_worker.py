import threading

import pytest

import api
from ui.workers.upload import UploadWorker
from utils.status import CONNECTION_FAILED, Tone

UPLOADED = (True, None)


class FakeApi:
    """Plays scripted results per NF-e for each api call; exceptions are raised."""

    def __init__(self, lookup=None, details=None, upload=None):
        self._lookup = {n: list(r) for n, r in (lookup or {}).items()}
        self._details = {n: list(r) for n, r in (details or {}).items()}
        self._upload = {n: list(r) for n, r in (upload or {}).items()}
        self.calls: list[tuple[str, str]] = []
        self.stops: list = []

    @staticmethod
    def _play(results: list):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def get_invoice_for_upload(self, session, invoice_num, stop=None):
        self.calls.append(("lookup", invoice_num))
        self.stops.append(stop)
        return self._play(self._lookup[invoice_num])

    def get_invoice_details(self, session, oid, stop=None):
        self.calls.append(("details", oid))
        return self._play(self._details.get(oid, [{"oid": oid}]))

    def upload_invoice(self, session, invoice_num, file_path, full_data, batch_date, stop=None):
        self.calls.append(("upload", invoice_num))
        return self._play(self._upload.get(invoice_num, [UPLOADED]))


@pytest.fixture
def folder(tmp_path):
    renamed = tmp_path / "renomeadas"
    renamed.mkdir()
    return renamed


def _images(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"img")


def _pending(n):
    return [(f"oid-{n}", "PENDENTE")]


class Run:
    def __init__(self, folder, fake, *, relogin=lambda: None, stop=None):
        self.events: list[tuple] = []
        self.stop = stop or threading.Event()
        UploadWorker(
            session=None,
            folder=str(folder),
            batch_date="2026-11-18T12:00:00.000Z",
            stop_event=self.stop,
            after_fn=lambda _delay, fn, *args: fn(*args),
            on_update=lambda n, tone, text, *progress: self.events.append(("row", n, tone, text)),
            on_done=lambda: self.events.append(("done",)),
            on_cancel=lambda: self.events.append(("cancel",)),
            on_session_lost=lambda: self.events.append(("lost",)),
            relogin=relogin,
            client=fake,
        ).run()


def _where(folder, name) -> str:
    for place in (folder, folder.parent / "pendentes", folder.parent / "nao-pendentes"):
        if (place / name).exists():
            return place.name
    return "missing"


# routing --------------------------------------------------------------------------

def test_pending_receipt_is_uploaded_and_moved(folder):
    _images(folder, "10.jpg")
    fake = FakeApi(lookup={"10": _pending(10)})

    run = Run(folder, fake)

    assert run.events == [("row", "10", Tone.OK, "Enviado"), ("done",)]
    assert _where(folder, "10.jpg") == "pendentes"
    assert fake.calls == [("lookup", "10"), ("details", "oid-10"), ("upload", "10")]


def test_receipt_with_other_status_is_moved_aside_without_upload(folder):
    _images(folder, "10.jpg")
    fake = FakeApi(lookup={"10": [("oid-10", "APROVADO")]})

    run = Run(folder, fake)

    assert run.events[0] == ("row", "10", Tone.WARNING, "APROVADO")
    assert _where(folder, "10.jpg") == "nao-pendentes"
    assert ("upload", "10") not in fake.calls


def test_receipt_not_found_stays(folder):
    _images(folder, "10.jpg")

    run = Run(folder, FakeApi(lookup={"10": [(None, "Não encontrada")]}))

    assert run.events[0] == ("row", "10", Tone.ERROR, "Não encontrada")
    assert _where(folder, "10.jpg") == "renomeadas"


def test_refused_upload_stays_with_server_message(folder):
    _images(folder, "10.jpg")
    fake = FakeApi(lookup={"10": _pending(10)}, upload={"10": [(False, "Canhoto já possui imagem")]})

    run = Run(folder, fake)

    assert run.events[0] == ("row", "10", Tone.ERROR, "Canhoto já possui imagem")
    assert _where(folder, "10.jpg") == "renomeadas"


def test_only_images_are_processed(folder):
    _images(folder, "10.jpg", "11.PNG", "notes.txt")
    fake = FakeApi(lookup={"10": _pending(10), "11": _pending(11)})

    run = Run(folder, fake)

    assert [e[1] for e in run.events if e[0] == "row"] == ["10", "11"]
    assert _where(folder, "notes.txt") == "renomeadas"


# connection -----------------------------------------------------------------------

@pytest.mark.parametrize("step", ["lookup", "upload"])
def test_connection_failure_keeps_the_file_and_continues(folder, step):
    _images(folder, "10.jpg", "11.jpg")
    failure = api.ConnectionFailed("down")
    fake = FakeApi(
        lookup={"10": [failure] if step == "lookup" else _pending(10), "11": _pending(11)},
        upload={"10": [failure]},
    )

    run = Run(folder, fake)

    assert run.events[0] == ("row", "10", Tone.CONNECTION, CONNECTION_FAILED)
    assert run.events[1] == ("row", "11", Tone.OK, "Enviado")
    assert _where(folder, "10.jpg") == "renomeadas"
    assert _where(folder, "11.jpg") == "pendentes"


def test_first_file_has_no_extra_attempt(folder):
    _images(folder, "10.jpg")
    fake = FakeApi(lookup={"10": [api.ConnectionFailed("down")]})

    Run(folder, fake)

    assert fake.calls == [("lookup", "10")]


def test_api_calls_receive_the_stop_event(folder):
    _images(folder, "10.jpg")
    fake = FakeApi(lookup={"10": _pending(10)})

    run = Run(folder, fake)

    assert fake.stops == [run.stop]


# session --------------------------------------------------------------------------

def test_expired_session_logs_in_again_and_uploads(folder):
    _images(folder, "10.jpg")
    relogins = []
    fake = FakeApi(lookup={"10": _pending(10)}, upload={"10": [api.SessionExpired("401"), UPLOADED]})

    run = Run(folder, fake, relogin=lambda: relogins.append(1))

    assert relogins == [1]
    assert run.events == [("row", "10", Tone.OK, "Enviado"), ("done",)]
    assert _where(folder, "10.jpg") == "pendentes"


def test_failed_relogin_stops_before_the_next_files(folder):
    _images(folder, "10.jpg", "11.jpg")

    def failing_login():
        raise ValueError("E-mail ou senha inválidos.")

    fake = FakeApi(lookup={"10": [api.SessionExpired("401")], "11": _pending(11)})

    run = Run(folder, fake, relogin=failing_login)

    assert run.events == [("lost",)]
    assert fake.calls == [("lookup", "10")]
    assert _where(folder, "10.jpg") == "renomeadas"
    assert _where(folder, "11.jpg") == "renomeadas"


# cancel ---------------------------------------------------------------------------

def test_stop_before_a_file_cancels(folder):
    _images(folder, "10.jpg")
    stop = threading.Event()
    stop.set()

    run = Run(folder, FakeApi(), stop=stop)

    assert run.events == [("cancel",)]
    assert _where(folder, "10.jpg") == "renomeadas"


def test_cancel_during_a_retry_wait_cancels(folder):
    _images(folder, "10.jpg", "11.jpg")
    fake = FakeApi(lookup={"10": [api.Cancelled()], "11": _pending(11)})

    run = Run(folder, fake)

    assert run.events == [("cancel",)]
    assert _where(folder, "11.jpg") == "renomeadas"
