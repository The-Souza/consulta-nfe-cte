import json
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

import drivers
from drivers import Delivery, DriverLookup, get_drivers, sheet_label

BASE = "https://project.supabase.test"
URL = f"{BASE}/rest/v1/entregas"
KEY = "sb_publishable_test"
UPDATED = "2026-11-19T20:10:57.104925+00:00"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(drivers, "SUPABASE_URL", BASE)
    monkeypatch.setattr(drivers, "SUPABASE_ANON_KEY", KEY)


def _row(nfe, driver="Motorista A", day="2026-11-12", cte=25000):
    return {"nfe": nfe, "cte": cte, "motorista": driver, "data_entrega": day}


def _serve(rows, updated=UPDATED):
    """Fake PostgREST for the entregas table: nfe gte/lte/in filters, order, limit and offset."""

    def callback(request):
        query = parse_qs(urlparse(request.url).query)
        if query["select"] == ["atualizado_em"]:
            return 200, {}, json.dumps([{"atualizado_em": updated}] if updated else [])
        selected = list(rows)
        for condition in query.get("nfe", []):
            op, _, value = condition.partition(".")
            if op == "gte":
                selected = [r for r in selected if r["nfe"] >= int(value)]
            elif op == "lte":
                selected = [r for r in selected if r["nfe"] <= int(value)]
            elif op == "in":
                wanted = {int(v) for v in value.strip("()").split(",")}
                selected = [r for r in selected if r["nfe"] in wanted]
        selected.sort(key=lambda r: r["nfe"])
        if "limit" in query:
            offset = int(query.get("offset", ["0"])[0])
            selected = selected[offset:offset + int(query["limit"][0])]
        return 200, {}, json.dumps(selected)

    responses.add_callback(responses.GET, URL, callback=callback)


def _data_calls():
    return [
        parse_qs(urlparse(call.request.url).query)
        for call in responses.calls
        if parse_qs(urlparse(call.request.url).query)["select"] != ["atualizado_em"]
    ]


# Configuration -------------------------------------------------------------------

@responses.activate
def test_without_configuration_is_off_and_makes_no_call(monkeypatch):
    monkeypatch.setattr(drivers, "SUPABASE_URL", "")
    monkeypatch.setattr(drivers, "SUPABASE_ANON_KEY", "")

    assert get_drivers([4110752]) == DriverLookup({}, None, "off")
    assert len(responses.calls) == 0


@responses.activate
def test_missing_key_alone_is_off(monkeypatch):
    monkeypatch.setattr(drivers, "SUPABASE_URL", BASE)
    monkeypatch.setattr(drivers, "SUPABASE_ANON_KEY", "")

    assert get_drivers([1]).state == "off"
    assert len(responses.calls) == 0


@responses.activate
def test_empty_list_makes_no_call(configured):
    assert get_drivers([]) == DriverLookup({}, None, "ok")
    assert len(responses.calls) == 0


@responses.activate
def test_sends_only_the_publishable_key(configured):
    _serve([_row(1)])

    get_drivers([1])

    for call in responses.calls:
        assert call.request.headers["apikey"] == KEY
        assert "Authorization" not in call.request.headers


# Range ---------------------------------------------------------------------------

@responses.activate
def test_range_is_read_with_gte_and_lte(configured):
    _serve([_row(100, "Ana"), _row(105, "Bia"), _row(200, "Fora")])

    lookup = get_drivers(range(100, 111))

    calls = _data_calls()
    assert len(calls) == 1
    assert calls[0]["nfe"] == ["gte.100", "lte.110"]
    assert lookup.state == "ok"
    assert lookup.deliveries == {
        100: Delivery("Ana", date(2026, 11, 12)),
        105: Delivery("Bia", date(2026, 11, 12)),
    }


@responses.activate
def test_unsorted_and_repeated_contiguous_numbers_are_one_range(configured):
    _serve([])

    get_drivers([5, 3, 4, 4])

    assert _data_calls()[0]["nfe"] == ["gte.3", "lte.5"]


@responses.activate
def test_large_range_is_paginated(configured):
    _serve([_row(n) for n in range(1, 2501)])

    lookup = get_drivers(range(1, 2501))

    calls = _data_calls()
    assert [c["offset"] for c in calls] == [["0"], ["1000"], ["2000"]]
    assert all(c["limit"] == ["1000"] for c in calls)
    assert len(lookup.deliveries) == 2500


@responses.activate
def test_range_with_an_exact_full_page_asks_once_more(configured):
    _serve([_row(n) for n in range(1, 1001)])

    lookup = get_drivers(range(1, 1001))

    assert [c["offset"] for c in _data_calls()] == [["0"], ["1000"]]
    assert len(lookup.deliveries) == 1000


# Lists ---------------------------------------------------------------------------

@responses.activate
def test_list_is_read_in_batches_of_200(configured):
    nfes = list(range(0, 900, 2))  # 450 numbers with gaps
    _serve([_row(n) for n in nfes])

    lookup = get_drivers(nfes)

    calls = _data_calls()
    sizes = [len(c["nfe"][0].removeprefix("in.(").removesuffix(")").split(",")) for c in calls]
    assert sizes == [200, 200, 50]
    assert len(lookup.deliveries) == 450


@responses.activate
def test_single_invoice_uses_in(configured):
    _serve([_row(7)])

    lookup = get_drivers([7])

    assert _data_calls()[0]["nfe"] == ["in.(7)"]
    assert 7 in lookup.deliveries


# Parsing -------------------------------------------------------------------------

@responses.activate
def test_empty_delivery_date_becomes_none(configured):
    _serve([_row(1, "Ana", None)])

    assert get_drivers([1]).deliveries == {1: Delivery("Ana", None)}


@responses.activate
def test_invoices_outside_the_table_are_left_out(configured):
    _serve([_row(1)])

    assert set(get_drivers([1, 50]).deliveries) == {1}


@responses.activate
def test_updated_at_is_the_latest_change_in_local_time(configured):
    _serve([_row(1)])

    updated_at = get_drivers([1]).updated_at

    expected = datetime(2026, 11, 19, 20, 10, 57, 104925, tzinfo=timezone.utc)
    assert updated_at == expected
    assert updated_at.utcoffset() == expected.astimezone().utcoffset()


@responses.activate
def test_updated_at_accepts_short_fractions_and_z(configured):
    _serve([_row(1)], updated="2026-11-19T20:10:57.1Z")

    assert get_drivers([1]).updated_at == datetime(2026, 11, 19, 20, 10, 57, 100000, tzinfo=timezone.utc)


@responses.activate
def test_empty_table_has_no_updated_at(configured):
    _serve([], updated=None)

    assert get_drivers([1]) == DriverLookup({}, None, "ok")


# Failures ------------------------------------------------------------------------

def _assert_failed(lookup, caplog):
    assert lookup == DriverLookup({}, None, "failed")
    assert any(record.levelname == "WARNING" for record in caplog.records)


@responses.activate
def test_http_error_fails_quietly(configured, caplog):
    responses.get(URL, status=401, json={"message": "Invalid API key"})

    _assert_failed(get_drivers([1]), caplog)


@responses.activate
def test_connection_error_fails_quietly(configured, caplog):
    responses.get(URL, body=requests.ConnectionError("offline"))

    _assert_failed(get_drivers([1]), caplog)


@responses.activate
def test_timeout_fails_quietly(configured, caplog):
    responses.get(URL, body=requests.Timeout("slow"))

    _assert_failed(get_drivers([1]), caplog)


@responses.activate
def test_invalid_json_fails_quietly(configured, caplog):
    responses.get(URL, body="<html>")

    _assert_failed(get_drivers([1]), caplog)


@responses.activate
def test_unexpected_payload_fails_quietly(configured, caplog):
    responses.get(URL, json={"rows": []})

    _assert_failed(get_drivers([1]), caplog)


@responses.activate
def test_invalid_date_fails_quietly(configured, caplog):
    _serve([_row(1, "Ana", "12/11/2026")])

    _assert_failed(get_drivers([1]), caplog)


@responses.activate
def test_failure_reading_updated_at_fails_the_whole_lookup(configured, caplog):
    _serve([_row(1)], updated="ontem")

    _assert_failed(get_drivers([1]), caplog)


# sheet_label ---------------------------------------------------------------------

NOW = datetime(2026, 11, 19, 17, 30)


@pytest.mark.parametrize(
    ("updated_at", "now", "expected"),
    [
        (datetime(2026, 11, 19, 14, 20), NOW, "planilha de hoje, 14:20"),
        (datetime(2026, 11, 18, 9, 5), NOW, "planilha de ontem, 09:05"),
        (datetime(2026, 11, 12, 9, 5), NOW, "planilha de 12/11, 09:05"),
        (datetime(2025, 11, 12, 9, 5), NOW, "planilha de 12/11/2025, 09:05"),
        (datetime(2026, 11, 30, 23, 59), datetime(2026, 12, 1, 8, 0), "planilha de ontem, 23:59"),
        (datetime(2025, 12, 31, 18, 0), datetime(2026, 1, 1, 8, 0), "planilha de ontem, 18:00"),
    ],
)
def test_sheet_label(updated_at, now, expected):
    assert sheet_label(updated_at, now) == expected


def test_sheet_label_without_updated_at_is_empty():
    assert sheet_label(None, NOW) == ""
