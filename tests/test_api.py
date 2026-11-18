import threading

import pytest
import requests
import responses

import api
from utils.status import SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK

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
