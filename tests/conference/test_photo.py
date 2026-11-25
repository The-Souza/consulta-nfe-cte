from datetime import date, datetime

import pytest

from conference.photo import DateLocked, Photo, Status, SystemInfo, status_of

TYPED = date(2026, 11, 14)
SYSTEM = date(2026, 11, 13)
CHECKED = datetime(2026, 11, 25, 9, 0)


def system(delivery: date | None = SYSTEM, state: str = "found") -> SystemInfo:
    return SystemInfo(state=state, delivery=delivery, checked_at=CHECKED)


def photo(**fields) -> Photo:
    base = dict(name="a.jpg", file_hash="h", nfe=4406833, nfe_source="qr", typed_date=TYPED)
    return Photo(**{**base, **fields})


class TestStatus:
    def test_ready_when_confirmed_with_invoice_and_date(self):
        assert status_of(photo(confirmed=True), duplicated=False) is Status.READY

    def test_to_check_until_confirmed(self):
        assert status_of(photo(), duplicated=False) is Status.TO_CHECK

    def test_a_valid_qr_and_a_system_date_still_need_confirmation(self):
        assert status_of(photo(typed_date=None, system=system()), duplicated=False) is Status.TO_CHECK

    def test_no_date(self):
        assert status_of(photo(typed_date=None, confirmed=True), duplicated=False) is Status.NO_DATE

    def test_a_system_without_date_still_needs_one(self):
        assert status_of(photo(typed_date=None, system=system(None)), duplicated=False) is Status.NO_DATE

    def test_duplicate_comes_before_date_and_confirmation(self):
        assert status_of(photo(confirmed=True), duplicated=True) is Status.DUPLICATE
        assert status_of(photo(typed_date=None), duplicated=True) is Status.DUPLICATE

    def test_unread_comes_before_duplicate(self):
        assert status_of(photo(nfe=None, nfe_source=None), duplicated=True) is Status.UNREAD

    def test_discarded_comes_first(self):
        assert status_of(photo(nfe=None, discarded=True), duplicated=True) is Status.DISCARDED

    def test_labels_are_in_portuguese(self):
        assert [s.label for s in Status] == ["Descartada", "Não lida", "Duplicata", "Sem data", "A conferir", "Pronta"]


class TestDate:
    def test_the_system_date_wins_and_locks_the_field(self):
        p = photo(system=system())
        assert (p.date, p.date_source, p.date_locked) == (SYSTEM, "system", True)

    def test_the_typed_date_when_the_system_has_none(self):
        p = photo(system=system(None))
        assert (p.date, p.date_source, p.date_locked) == (TYPED, "typed", False)

    def test_no_date_at_all(self):
        p = photo(typed_date=None)
        assert (p.date, p.date_source, p.date_locked) == (None, None, False)

    def test_typing_a_date_undoes_the_confirmation(self):
        p = photo(confirmed=True)
        p.set_typed_date(date(2026, 11, 15))
        assert p.typed_date == date(2026, 11, 15) and not p.confirmed

    def test_typing_the_same_date_keeps_the_confirmation(self):
        p = photo(confirmed=True)
        p.set_typed_date(TYPED)
        assert p.confirmed

    def test_a_locked_date_cannot_be_typed(self):
        p = photo(system=system())
        with pytest.raises(DateLocked):
            p.set_typed_date(date(2026, 11, 15))
        assert p.typed_date == TYPED


class TestNfe:
    def test_typing_another_number_marks_it_typed_and_resets_the_review(self):
        p = photo(confirmed=True, system=system())
        p.set_nfe(4406834)
        assert (p.nfe, p.nfe_source, p.confirmed, p.system) == (4406834, "typed", False, None)

    def test_the_same_number_changes_nothing(self):
        p = photo(confirmed=True, system=system())
        p.set_nfe(4406833)
        assert (p.nfe_source, p.confirmed, p.system) == ("qr", True, system())

    def test_clearing_the_number_makes_it_unread(self):
        p = photo(confirmed=True)
        p.set_nfe(None)
        assert (p.nfe, p.nfe_source, p.confirmed) == (None, None, False)

    @pytest.mark.parametrize("bad", [0, -1, 1_000_000_000])
    def test_rejects_numbers_outside_nine_digits(self, bad):
        with pytest.raises(ValueError):
            photo().set_nfe(bad)


def test_system_lookup_without_delivery_keeps_the_typed_date_editable():
    p = photo(system=system(None, state="not_found"))
    p.set_typed_date(date(2026, 11, 10))
    assert p.date == date(2026, 11, 10)
