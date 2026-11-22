import json
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses

from sheet_sync.diff import Changes, Stored
from sheet_sync.settings import SyncConfig
from sheet_sync.sheet import Entry
from sheet_sync.supabase import SendResult, SupabaseError, fetch_stored, send

SECRET = "sb_secret_test"
CONFIG = SyncConfig("https://example.supabase.co", SECRET, "")
TABLE = "https://example.supabase.co/rest/v1/entregas"
NOW = datetime(2026, 11, 22, 17, 20, tzinfo=timezone.utc)


def _row(i, nfe=None, cte=None, driver="Ana", day="2026-11-22"):
    return {"id": f"id-{i}", "nfe": nfe if nfe is not None else 1000 + i, "cte": cte, "motorista": driver,
            "data_entrega": day}


def _query(call) -> dict[str, list[str]]:
    return parse_qs(urlsplit(call.request.url).query)


def _entry(nfe, cte=None, driver="Ana", day=date(2026, 11, 22)):
    return Entry(nfe=nfe, cte=cte, driver=driver, date=day, line=2)


# fetch_stored -------------------------------------------------------------------

@responses.activate
def test_fetch_stored_reads_every_page():
    responses.get(TABLE, json=[_row(i) for i in range(1000)])
    responses.get(TABLE, json=[_row(1000), _row(1001, nfe=None, cte=5533)])

    stored = fetch_stored(CONFIG)

    assert len(stored) == 1002
    assert [_query(c)["offset"] for c in responses.calls] == [["0"], ["1000"]]
    first = _query(responses.calls[0])
    assert first["select"] == ["id,nfe,cte,motorista,data_entrega"]
    assert first["order"] == ["id"]
    assert first["limit"] == ["1000"]


@responses.activate
def test_fetch_stored_stops_on_an_empty_page():
    responses.get(TABLE, json=[_row(i) for i in range(1000)])
    responses.get(TABLE, json=[])

    assert len(fetch_stored(CONFIG)) == 1000
    assert len(responses.calls) == 2


@responses.activate
def test_fetch_stored_parses_rows_with_empty_values():
    responses.get(TABLE, json=[
        {"id": "a", "nfe": 100, "cte": 25540, "motorista": "Ana", "data_entrega": "2026-11-22"},
        {"id": "b", "nfe": None, "cte": 5533, "motorista": "Bia", "data_entrega": None},
    ])

    assert fetch_stored(CONFIG) == [
        Stored(id="a", nfe=100, cte=25540, driver="Ana", date=date(2026, 11, 22)),
        Stored(id="b", nfe=None, cte=5533, driver="Bia", date=None),
    ]


@responses.activate
def test_requests_carry_the_key_only_in_the_apikey_header():
    responses.get(TABLE, json=[])

    fetch_stored(CONFIG)

    headers = responses.calls[0].request.headers
    assert headers["apikey"] == SECRET
    assert "Authorization" not in headers
    assert SECRET not in responses.calls[0].request.url


@pytest.mark.parametrize(("response", "message"), [
    ({"status": 401}, "A chave não tem permissão"),
    ({"status": 403}, "A chave não tem permissão"),
    ({"status": 500}, "HTTP 500"),
    ({"body": requests.exceptions.ConnectionError("down")}, "Sem conexão com o Supabase"),
    ({"body": requests.exceptions.ReadTimeout("slow")}, "Sem conexão com o Supabase"),
    ({"body": "not json"}, "resposta inesperada"),
    ({"json": [{"id": "a"}]}, "resposta inesperada"),
])
@responses.activate
def test_fetch_stored_errors_become_screen_messages(response, message):
    responses.get(TABLE, **response)

    with pytest.raises(SupabaseError, match=message) as error:
        fetch_stored(CONFIG)

    assert SECRET not in str(error.value)


# send ---------------------------------------------------------------------------

def _bodies():
    return [json.loads(c.request.body) for c in responses.calls]


@responses.activate
def test_send_without_changes_makes_no_request():
    assert send(Changes(new=[], updated=[], unchanged=5), CONFIG, now=NOW) == SendResult(written=0)
    assert len(responses.calls) == 0


@responses.activate
def test_send_inserts_new_rows_in_batches_of_1000():
    responses.post(TABLE, status=201)

    result = send(Changes(new=[_entry(i) for i in range(1, 2501)], updated=[], unchanged=0), CONFIG, now=NOW)

    assert result == SendResult(written=2500)
    assert [len(b) for b in _bodies()] == [1000, 1000, 500]
    call = responses.calls[0]
    assert "on_conflict" not in _query(call)
    assert call.request.headers["Prefer"] == "return=minimal"
    assert call.request.headers["apikey"] == SECRET
    assert _bodies()[0][0] == {"nfe": 1, "cte": None, "motorista": "Ana", "data_entrega": "2026-11-22",
                               "atualizado_em": "2026-11-22T17:20:00+00:00"}


@responses.activate
def test_send_updates_changed_rows_by_id():
    responses.post(TABLE, status=200)
    entry = _entry(100, cte=25540, driver="Bia", day=None)

    result = send(Changes(new=[], updated=[("abc", entry)], unchanged=0), CONFIG, now=NOW)

    assert result == SendResult(written=1)
    call = responses.calls[0]
    assert _query(call)["on_conflict"] == ["id"]
    assert call.request.headers["Prefer"] == "resolution=merge-duplicates,return=minimal"
    assert _bodies() == [[{"id": "abc", "nfe": 100, "cte": 25540, "motorista": "Bia", "data_entrega": None,
                           "atualizado_em": "2026-11-22T17:20:00+00:00"}]]


@responses.activate
def test_send_never_mixes_new_and_updated_rows_in_one_request():
    responses.post(TABLE, status=201)

    send(Changes(new=[_entry(1)], updated=[("abc", _entry(2))], unchanged=0), CONFIG, now=NOW)

    keys = [{tuple(sorted(row)) for row in body} for body in _bodies()]
    assert all(len(k) == 1 for k in keys)  # every row of a request has the same keys
    assert len(responses.calls) == 2


@pytest.mark.parametrize(("failure", "message"), [
    ({"status": 401}, "A chave não tem permissão"),
    ({"status": 500}, "HTTP 500"),
    ({"body": requests.exceptions.ConnectTimeout("slow")}, "Sem conexão com o Supabase"),
])
@responses.activate
def test_send_stops_at_the_first_failure_and_reports_what_was_written(failure, message):
    responses.post(TABLE, status=201)
    responses.post(TABLE, **failure)

    result = send(Changes(new=[_entry(i) for i in range(1, 2501)], updated=[], unchanged=0), CONFIG, now=NOW)

    assert result.written == 1000
    assert message in result.error
    assert SECRET not in result.error
    assert len(responses.calls) == 2
