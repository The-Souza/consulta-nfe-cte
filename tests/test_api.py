import base64
import json
import threading

import pytest
import requests
import responses
import urllib3

import api
from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK

URL = "https://api.test/canhotos"


@pytest.fixture
def api_urls(monkeypatch):
    monkeypatch.setattr(api, "CANHOTOS_URL", URL)
    monkeypatch.setattr(api, "QUERY_HEADERS", {"programa": "test"})


@pytest.fixture
def waits(monkeypatch):
    """Replaces the retry pause with a recorder, so tests never sleep."""
    recorded: list[float] = []
    monkeypatch.setattr(api, "_wait", lambda seconds, stop=None: recorded.append(seconds))
    return recorded


@pytest.fixture
def session():
    return requests.Session()


def _get(session, **kwargs):
    return api._get_json(session, URL, **kwargs)


# _get_json: success and retries -------------------------------------------------

@responses.activate
def test_get_json_returns_payload(session, waits):
    responses.get(URL, json={"data": [1]})

    assert _get(session) == {"data": [1]}
    assert waits == []


@responses.activate
def test_get_json_sends_params_and_headers(session, waits):
    responses.get(
        URL, json={},
        match=[responses.matchers.query_param_matcher({"numero": "10"}),
               responses.matchers.header_matcher({"programa": "x"})],
    )

    assert _get(session, params={"numero": 10}, headers={"programa": "x"}) == {}


@responses.activate
def test_get_json_retries_timeouts_until_success(session, waits):
    responses.get(URL, body=requests.exceptions.ReadTimeout())
    responses.get(URL, body=requests.exceptions.ConnectTimeout())
    responses.get(URL, json={"ok": True})

    assert _get(session) == {"ok": True}
    assert len(responses.calls) == 3
    assert waits == [1, 2]


@responses.activate
def test_get_json_retries_connection_errors(session, waits):
    responses.get(URL, body=requests.exceptions.ConnectionError("reset"))
    responses.get(URL, json={"ok": True})

    assert _get(session) == {"ok": True}
    assert waits == [1]


@responses.activate
def test_get_json_gives_up_after_three_retries(session, waits):
    responses.get(URL, status=500)

    with pytest.raises(api.ConnectionFailed):
        _get(session)
    assert len(responses.calls) == 4
    assert waits == [1, 2, 4]


@responses.activate
def test_get_json_retries_server_errors(session, waits):
    responses.get(URL, status=503)
    responses.get(URL, json={"ok": True})

    assert _get(session) == {"ok": True}
    assert waits == [1]


@responses.activate
def test_get_json_retries_html_response(session, waits):
    responses.get(URL, body="<html>login</html>", content_type="text/html")
    responses.get(URL, json={"ok": True})

    assert _get(session) == {"ok": True}
    assert waits == [1]


@responses.activate
def test_get_json_html_every_time_is_connection_failure(session, waits):
    responses.get(URL, body="<html>login</html>", content_type="text/html")

    with pytest.raises(api.ConnectionFailed):
        _get(session)
    assert len(responses.calls) == 4


# _get_json: rate limit ----------------------------------------------------------

@pytest.mark.parametrize(
    ("retry_after", "expected_wait"),
    [("7", 7), ("120", api.MAX_RETRY_AFTER), ("Wed, 21 Oct 2026 07:28:00 GMT", 1), (None, 1)],
)
@responses.activate
def test_get_json_waits_for_retry_after(session, waits, retry_after, expected_wait):
    headers = {"Retry-After": retry_after} if retry_after else {}
    responses.get(URL, status=429, headers=headers)
    responses.get(URL, json={"ok": True})

    assert _get(session) == {"ok": True}
    assert waits == [expected_wait]


# _get_json: no retry ------------------------------------------------------------

@pytest.mark.parametrize("status", [401, 403])
@responses.activate
def test_get_json_session_expired_is_not_retried(session, waits, status):
    responses.get(URL, status=status)

    with pytest.raises(api.SessionExpired):
        _get(session)
    assert len(responses.calls) == 1
    assert waits == []


@responses.activate
def test_get_json_other_client_errors_are_not_retried(session, waits):
    responses.get(URL, status=404)

    with pytest.raises(requests.HTTPError):
        _get(session)
    assert len(responses.calls) == 1


@responses.activate
def test_get_json_stops_when_the_wait_is_cancelled(session, monkeypatch):
    def cancelled_wait(seconds, stop=None):
        raise api.Cancelled()

    monkeypatch.setattr(api, "_wait", cancelled_wait)
    responses.get(URL, status=500)

    with pytest.raises(api.Cancelled):
        _get(session)
    assert len(responses.calls) == 1


# get_invoice ----------------------------------------------------------------------

def _invoice(**item):
    return {"data": [item]}


@responses.activate
def test_get_invoice_with_cte(session, waits, api_urls):
    responses.get(URL, json=_invoice(numeroCte=123, possuiImagem="Sim"))

    assert api.get_invoice(session, 10) == ("123", SEARCH_OK, "Sim")
    assert responses.calls[0].request.params == {"limit": "40", "numero": "10", "offset": "0"}


@responses.activate
def test_get_invoice_without_cte(session, waits, api_urls):
    responses.get(URL, json=_invoice(numeroCte=None, possuiImagem="Não"))

    assert api.get_invoice(session, 10) == ("-", SEARCH_NO_CTE, "Não")


@responses.activate
def test_get_invoice_empty_twice_is_not_found(session, waits, api_urls):
    responses.get(URL, json={"data": []})

    assert api.get_invoice(session, 10) == ("-", SEARCH_NOT_FOUND, "-")
    assert len(responses.calls) == 2
    assert waits == [0.5]


@responses.activate
def test_get_invoice_empty_then_found(session, waits, api_urls):
    responses.get(URL, json={"data": []})
    responses.get(URL, json=_invoice(numeroCte=123, possuiImagem="Sim"))

    assert api.get_invoice(session, 10) == ("123", SEARCH_OK, "Sim")
    assert waits == [0.5]


@responses.activate
def test_get_invoice_retries_unstable_server(session, waits, api_urls):
    responses.get(URL, status=502)
    responses.get(URL, json=_invoice(numeroCte=123, possuiImagem="Sim"))

    assert api.get_invoice(session, 10) == ("123", SEARCH_OK, "Sim")
    assert waits == [1]


@responses.activate
def test_get_invoice_raises_connection_failed(session, waits, api_urls):
    responses.get(URL, body=requests.exceptions.ConnectTimeout())

    with pytest.raises(api.ConnectionFailed):
        api.get_invoice(session, 10)


# get_invoice_for_upload / get_invoice_details --------------------------------------

@responses.activate
def test_get_invoice_for_upload_returns_oid_and_status(session, waits, api_urls):
    responses.get(URL, json=_invoice(oid="abc", status="PENDENTE"))

    assert api.get_invoice_for_upload(session, "10") == ("abc", "PENDENTE")


@responses.activate
def test_get_invoice_for_upload_not_found(session, waits, api_urls):
    responses.get(URL, json={"data": []})

    assert api.get_invoice_for_upload(session, "10") == (None, "Não encontrada")


@responses.activate
def test_get_invoice_for_upload_retries_unstable_server(session, waits, api_urls):
    responses.get(URL, status=500)
    responses.get(URL, json=_invoice(oid="abc", status="PENDENTE"))

    assert api.get_invoice_for_upload(session, "10") == ("abc", "PENDENTE")


@responses.activate
def test_get_invoice_details_uses_canhoto_program(session, waits, api_urls):
    responses.get(
        f"{URL}/abc", json={"oid": "abc"},
        match=[responses.matchers.header_matcher({"programa": "Canhoto"})],
    )

    assert api.get_invoice_details(session, "abc") == {"oid": "abc"}


@responses.activate
def test_get_invoice_details_session_expired(session, waits, api_urls):
    responses.get(f"{URL}/abc", status=401)

    with pytest.raises(api.SessionExpired):
        api.get_invoice_details(session, "abc")


# upload_invoice -------------------------------------------------------------------

SAVE_URL = f"{URL}/salvar"


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "10.jpg"
    path.write_bytes(b"fake-image")
    return path


def _upload(session, image, delivery_date=None):
    full_data = {"oid": "abc", "documentoIndustria": {"dataEntrega": delivery_date}}
    return api.upload_invoice(session, "10", image, full_data, "2026-11-18T12:00:00.000Z")


def _refused():
    reason = urllib3.exceptions.NewConnectionError(None, "connection refused")
    return requests.exceptions.ConnectionError(urllib3.exceptions.MaxRetryError(None, SAVE_URL, reason=reason))


@responses.activate
def test_upload_sends_image_and_keeps_the_system_date(session, waits, api_urls, image):
    responses.post(SAVE_URL, json={})

    assert _upload(session, image, delivery_date="2026-11-01T12:00:00.000Z") == (True, None)
    body = json.loads(responses.calls[0].request.body)
    assert body["base64"] == base64.b64encode(b"fake-image").decode()
    assert body["nomeImagem"] == "10.jpeg"
    assert body["documentoIndustria"]["dataEntrega"] == "2026-11-01T12:00:00.000Z"
    assert responses.calls[0].request.headers["programa"] == "Canhoto"


@responses.activate
def test_upload_fills_the_date_only_when_empty(session, waits, api_urls, image):
    responses.post(SAVE_URL, json={})

    _upload(session, image)

    body = json.loads(responses.calls[0].request.body)
    assert body["documentoIndustria"]["dataEntrega"] == "2026-11-18T12:00:00.000Z"


@responses.activate
def test_upload_retries_when_the_connection_is_refused(session, waits, api_urls, image):
    responses.post(SAVE_URL, body=_refused())
    responses.post(SAVE_URL, json={})

    assert _upload(session, image) == (True, None)
    assert len(responses.calls) == 2
    assert waits == [1]


@responses.activate
def test_upload_gives_up_after_connect_timeouts(session, waits, api_urls, image):
    responses.post(SAVE_URL, body=requests.exceptions.ConnectTimeout())

    with pytest.raises(api.ConnectionFailed):
        _upload(session, image)
    assert len(responses.calls) == 4
    assert waits == [1, 2, 4]


@pytest.mark.parametrize(
    "error",
    [requests.exceptions.ReadTimeout(), requests.exceptions.ConnectionError("Connection aborted")],
)
@responses.activate
def test_upload_does_not_retry_after_the_request_may_have_arrived(session, waits, api_urls, image, error):
    responses.post(SAVE_URL, body=error)

    with pytest.raises(api.ConnectionFailed):
        _upload(session, image)
    assert len(responses.calls) == 1
    assert waits == []


@pytest.mark.parametrize("status", [400, 500, 502])
@responses.activate
def test_upload_returns_server_message_without_retry(session, waits, api_urls, image, status):
    responses.post(SAVE_URL, status=status, body="Canhoto já possui imagem")

    assert _upload(session, image) == (False, "Canhoto já possui imagem")
    assert len(responses.calls) == 1


@responses.activate
def test_upload_session_expired(session, waits, api_urls, image):
    responses.post(SAVE_URL, status=403)

    with pytest.raises(api.SessionExpired):
        _upload(session, image)


# call_with_relogin ----------------------------------------------------------------

class _Calls:
    """fn() that plays a scripted list of results; exceptions are raised."""

    def __init__(self, *results):
        self._results = list(results)
        self.count = 0

    def __call__(self):
        self.count += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_call_with_relogin_returns_without_relogin():
    relogins = []

    assert api.call_with_relogin(_Calls("ok"), lambda: relogins.append(1)) == "ok"
    assert relogins == []


def test_call_with_relogin_logs_in_again_and_repeats():
    fn = _Calls(api.SessionExpired("401"), "ok")
    relogins = []

    assert api.call_with_relogin(fn, lambda: relogins.append(1)) == "ok"
    assert relogins == [1]
    assert fn.count == 2


def test_call_with_relogin_failed_login_is_session_lost():
    fn = _Calls(api.SessionExpired("401"))

    def failing_login():
        raise ValueError("E-mail ou senha inválidos.")

    with pytest.raises(api.SessionLost):
        api.call_with_relogin(fn, failing_login)
    assert fn.count == 1


def test_call_with_relogin_expired_again_is_session_lost():
    fn = _Calls(api.SessionExpired("401"), api.SessionExpired("401"))
    relogins = []

    with pytest.raises(api.SessionLost):
        api.call_with_relogin(fn, lambda: relogins.append(1))
    assert relogins == [1]


def test_call_with_relogin_keeps_other_errors():
    with pytest.raises(api.ConnectionFailed):
        api.call_with_relogin(_Calls(api.ConnectionFailed("down")), lambda: None)


# warm_up --------------------------------------------------------------------------

@responses.activate
def test_warm_up_makes_one_light_call(session, waits, api_urls):
    responses.get(URL, json={"data": []})

    api.warm_up(session, 10)

    assert len(responses.calls) == 1
    assert responses.calls[0].request.params == {"limit": "1", "numero": "10", "offset": "0"}


@pytest.mark.parametrize(
    "body", [requests.exceptions.ConnectTimeout(), requests.exceptions.ConnectionError("reset")],
)
@responses.activate
def test_warm_up_ignores_connection_errors(session, waits, api_urls, body):
    responses.get(URL, body=body)

    api.warm_up(session, 10)

    assert len(responses.calls) == 1
    assert waits == []


@pytest.mark.parametrize("status", [401, 500])
@responses.activate
def test_warm_up_ignores_error_status(session, waits, api_urls, status):
    responses.get(URL, status=status)

    api.warm_up(session, 10)

    assert len(responses.calls) == 1


# friendly_error -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api.ConnectionFailed("HTTP 502"), CONNECTION_FAILED),
        (api.SessionExpired("HTTP 401"), "Sessão expirada"),
        (requests.exceptions.ConnectionError(), "Sem conexão com o servidor"),
        (requests.exceptions.Timeout(), "Tempo de resposta esgotado"),
        (ValueError("x" * 100), "x" * 80),
    ],
)
def test_friendly_error(error, expected):
    assert api.friendly_error(error) == expected


# _wait --------------------------------------------------------------------------

def test_wait_raises_cancelled_when_stop_is_set():
    stop = threading.Event()
    stop.set()

    with pytest.raises(api.Cancelled):
        api._wait(10, stop)


def test_wait_returns_when_stop_is_not_set():
    api._wait(0, threading.Event())


def test_wait_without_stop_sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr(api.time, "sleep", slept.append)

    api._wait(2)

    assert slept == [2]
