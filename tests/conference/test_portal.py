from datetime import date, datetime

import pytest
import requests

import api
from conference.portal import check

NOW = datetime(2026, 11, 25, 10, 0)
SESSION = object()


class FakeApi:
    """Plays scripted results for the two read calls; exceptions are raised. Writing is not allowed."""

    def __init__(self, lookup, details=None):
        self._lookup = list(lookup)
        self._details = list(details or [])
        self.calls: list[tuple] = []

    @staticmethod
    def _play(results: list):
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def get_invoice_for_upload(self, session, invoice_num, stop=None):
        self.calls.append(("lookup", invoice_num, stop))
        return self._play(self._lookup)

    def get_invoice_details(self, session, oid, stop=None):
        self.calls.append(("details", oid, stop))
        return self._play(self._details)

    def upload_invoice(self, *args, **kwargs):
        raise AssertionError("the review must never send anything")


def run(fake: FakeApi, relogin=lambda: None, stop=None):
    return check(SESSION, 4406833, relogin=relogin, stop=stop, client=fake, now=lambda: NOW)


def details(delivery) -> dict:
    return {"oid": "abc", "documentoIndustria": {"dataEntrega": delivery}}


class TestStates:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2026-11-14T12:00:00.000Z", date(2026, 11, 14)),  # as the app itself writes it
            ("2026-11-14T03:00:00.000Z", date(2026, 11, 14)),  # midnight in Brazil
            ("2026-11-14T02:00:00.000Z", date(2026, 11, 13)),  # still the 13th in Brazil
            ("2026-11-14T00:00:00-03:00", date(2026, 11, 14)),
            ("2026-11-14", date(2026, 11, 14)),
            ("14/11/2026", date(2026, 11, 14)),
        ],
    )
    def test_found_with_a_delivery_date(self, raw, expected):
        info = run(FakeApi([("abc", "PENDENTE")], [details(raw)]))
        assert (info.state, info.delivery, info.checked_at) == ("found", expected, NOW)

    @pytest.mark.parametrize("payload", [details(None), details(""), {"oid": "abc", "documentoIndustria": {}}, {}])
    def test_found_without_a_delivery_date(self, payload):
        info = run(FakeApi([("abc", "PENDENTE")], [payload]))
        assert (info.state, info.delivery) == ("found", None)

    def test_an_unreadable_date_counts_as_none_and_is_logged(self, caplog):
        info = run(FakeApi([("abc", "PENDENTE")], [details("amanhã")]))
        assert (info.state, info.delivery) == ("found", None)
        assert "amanhã" in caplog.text

    def test_not_found(self):
        fake = FakeApi([(None, "Não encontrada")])
        assert run(fake).state == "not_found"
        assert [c[0] for c in fake.calls] == ["lookup"]

    def test_already_approved_skips_the_details(self):
        fake = FakeApi([("abc", "APROVADO")])
        info = run(fake)
        assert (info.state, info.delivery, info.status) == ("approved", None, "APROVADO")
        assert [c[0] for c in fake.calls] == ["lookup"]

    def test_a_pending_receipt_keeps_its_status(self):
        assert run(FakeApi([("abc", "PENDENTE")], [details(None)])).status == "PENDENTE"

    def test_any_other_status_will_not_be_sent_and_skips_the_details(self):
        """Only PENDENTE takes an image: the review warns before the send step refuses it."""
        fake = FakeApi([("abc", "EM ANALISE")])
        info = run(fake)
        assert (info.state, info.delivery, info.status) == ("other", None, "EM ANALISE")
        assert [c[0] for c in fake.calls] == ["lookup"]

    @pytest.mark.parametrize("where", ["lookup", "details"])
    def test_connection_failure_is_unavailable(self, where):
        failure = api.ConnectionFailed("timeout")
        fake = FakeApi([failure] if where == "lookup" else [("abc", "PENDENTE")], [failure])
        assert run(fake).state == "unavailable"

    @pytest.mark.parametrize("where", ["lookup", "details"])
    @pytest.mark.parametrize(
        "failure",
        [
            requests.HTTPError("404 Client Error"),
            requests.exceptions.ChunkedEncodingError("response cut mid-transfer"),
            requests.TooManyRedirects("redirect loop"),
        ],
        ids=["http-error", "cut-response", "redirect-loop"],
    )
    def test_any_other_request_failure_is_unavailable(self, where, failure):
        fake = FakeApi([failure] if where == "lookup" else [("abc", "PENDENTE")], [failure])
        assert run(fake).state == "unavailable"


class TestCalls:
    def test_asks_for_the_invoice_number_as_text_and_passes_the_stop_event(self):
        stop = object()
        fake = FakeApi([("abc", "PENDENTE")], [details(None)])
        run(fake, stop=stop)
        assert fake.calls == [("lookup", "4406833", stop), ("details", "abc", stop)]

    def test_an_expired_session_logs_in_again_once(self):
        logins = []
        fake = FakeApi([api.SessionExpired("401"), ("abc", "PENDENTE")], [details("2026-11-14")])
        info = run(fake, relogin=lambda: logins.append(1))
        assert info.delivery == date(2026, 11, 14) and logins == [1]

    @pytest.mark.parametrize("error", [api.Cancelled(), api.SessionLost("no")])
    def test_cancel_and_lost_session_reach_the_caller(self, error):
        with pytest.raises(type(error)):
            run(FakeApi([error]))
