import threading

import pytest
import requests
import responses

import api

URL = "https://api.test/canhotos"


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
