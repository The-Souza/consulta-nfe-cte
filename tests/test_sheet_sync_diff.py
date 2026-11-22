from datetime import date

from sheet_sync.diff import Changes, Stored, compare
from sheet_sync.sheet import Entry

DAY = date(2026, 11, 22)


def _entry(nfe=100, cte=25540, driver="Ana", day=DAY, line=2):
    return Entry(nfe=nfe, cte=cte, driver=driver, date=day, line=line)


def _stored(id="id-1", nfe=100, cte=25540, driver="Ana", day=DAY):
    return Stored(id=id, nfe=nfe, cte=cte, driver=driver, date=day)


def test_an_invoice_missing_from_the_table_is_new():
    entry = _entry()

    assert compare([entry], []) == Changes(new=[entry], updated=[], unchanged=0)


def test_an_identical_invoice_is_unchanged():
    assert compare([_entry()], [_stored()]) == Changes(new=[], updated=[], unchanged=1)


def test_a_changed_driver_is_updated_with_the_table_id():
    entry = _entry(driver="Bia")

    assert compare([entry], [_stored(id="abc")]) == Changes(new=[], updated=[("abc", entry)], unchanged=0)


def test_a_changed_date_is_updated():
    entry = _entry(day=date(2026, 11, 23))

    assert compare([entry], [_stored()]).updated == [("id-1", entry)]


def test_a_date_removed_from_the_sheet_is_updated():
    entry = _entry(day=None)

    assert compare([entry], [_stored()]).updated == [("id-1", entry)]


def test_a_changed_cte_is_updated():
    entry = _entry(cte=5533)

    assert compare([entry], [_stored()]).updated == [("id-1", entry)]


def test_a_cte_added_to_an_invoice_is_updated():
    entry = _entry(cte=25540)

    assert compare([entry], [_stored(cte=None)]).updated == [("id-1", entry)]


def test_a_load_row_matches_the_stored_row_with_the_same_cte_and_no_invoice():
    entry = _entry(nfe=None, cte=5533, driver="Caio")

    assert compare([entry], [_stored(id="load", nfe=None, cte=5533, driver="Davi")]).updated == [("load", entry)]


def test_a_load_row_does_not_match_an_invoice_row_with_the_same_cte():
    # The invoice row keeps its own match; the load row is a separate row in the table
    load = _entry(nfe=None, cte=25540)

    assert compare([load], [_stored(nfe=100, cte=25540)]) == Changes(new=[load], updated=[], unchanged=0)


def test_an_invoice_does_not_match_a_load_row_with_the_same_cte():
    entry = _entry(nfe=100, cte=5533)

    assert compare([entry], [_stored(nfe=None, cte=5533)]).new == [entry]


def test_a_mix_of_new_updated_and_unchanged_rows_keeps_the_sheet_order():
    same, changed, fresh = _entry(nfe=1, line=2), _entry(nfe=2, driver="Bia", line=3), _entry(nfe=3, line=4)
    stored = [_stored(id="b", nfe=2), _stored(id="a", nfe=1), _stored(id="z", nfe=99)]

    assert compare([same, changed, fresh], stored) == Changes(new=[fresh], updated=[("b", changed)], unchanged=1)


def test_table_rows_missing_from_the_sheet_are_left_alone():
    assert compare([], [_stored()]) == Changes(new=[], updated=[], unchanged=0)
