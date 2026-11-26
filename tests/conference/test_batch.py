from datetime import date, datetime

import pytest

from conference.batch import Batch, Chip, DuplicateUnresolved, MissingField
from conference.photo import Photo, Status, SystemInfo

D13, D14, D15 = date(2026, 11, 13), date(2026, 11, 14), date(2026, 11, 15)


def p(name: str, nfe: int | None = None, typed: date | None = None, confirmed=False, system_date=None, **kw):
    system = SystemInfo("found", system_date, datetime(2026, 11, 25)) if system_date else None
    return Photo(name=name, file_hash=name, nfe=nfe, nfe_source="qr" if nfe else None, typed_date=typed,
                 confirmed=confirmed, system=system, **kw)


def batch(*photos: Photo) -> Batch:
    return Batch(photos)


class TestOrderAndAdd:
    def test_keeps_photos_in_name_order_ignoring_case(self):
        b = batch(p("b.jpg"), p("C.jpg"), p("a.jpg"))
        assert [x.name for x in b.visible()] == ["a.jpg", "b.jpg", "C.jpg"]

    def test_added_photos_take_their_place_in_order(self):
        b = batch(p("a.jpg"), p("c.jpg"))
        b.add(p("b.jpg"))
        assert [x.name for x in b.visible()] == ["a.jpg", "b.jpg", "c.jpg"]

    def test_adding_an_existing_name_replaces_it(self):
        b = batch(p("a.jpg", nfe=1))
        b.add(p("a.jpg", nfe=2))
        assert len(b) == 1 and b.photo("a.jpg").nfe == 2


def test_rows_pair_each_visible_photo_with_its_status_in_order():
    b = batch(p("c.jpg", nfe=1), p("a.jpg", nfe=1), p("b.jpg"), p("d.jpg", nfe=2, discarded=True))
    assert [(photo.name, status) for photo, status in b.rows()] == [
        ("a.jpg", Status.DUPLICATE), ("b.jpg", Status.UNREAD), ("c.jpg", Status.DUPLICATE)]


class TestDuplicates:
    def test_same_invoice_on_two_photos(self):
        b = batch(p("a.jpg", 1), p("b.jpg", 1), p("c.jpg", 2), p("d.jpg"))
        assert b.duplicates() == {1: ["a.jpg", "b.jpg"]}
        assert b.status("a.jpg") is Status.DUPLICATE and b.status("c.jpg") is Status.NO_DATE

    def test_ends_when_one_is_discarded(self):
        b = batch(p("a.jpg", 1, D14), p("b.jpg", 1))
        b.discard("b.jpg")
        assert b.duplicates() == {} and b.status("a.jpg") is Status.TO_CHECK

    def test_ends_when_one_number_is_corrected(self):
        b = batch(p("a.jpg", 1), p("b.jpg", 1))
        b.photo("b.jpg").set_nfe(2)
        assert b.duplicates() == {}


class TestChips:
    def make(self) -> Batch:
        return batch(
            p("1.jpg"),                                  # unread
            p("2.jpg", 1), p("3.jpg", 1),                # duplicates
            p("4.jpg", 2),                               # no date
            p("5.jpg", 3, D14),                          # to check
            p("6.jpg", 4, D14, confirmed=True),          # ready
            p("7.jpg", 5, D14, confirmed=True, discarded=True),
        )

    def test_counts(self):
        assert self.make().counts() == {
            Chip.ALL: 6, Chip.ATTENTION: 3, Chip.NO_DATE: 1, Chip.TO_CHECK: 1, Chip.READY: 1,
        }

    @pytest.mark.parametrize(
        "chip, names",
        [
            (Chip.ALL, ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg"]),
            (Chip.ATTENTION, ["1.jpg", "2.jpg", "3.jpg"]),
            (Chip.NO_DATE, ["4.jpg"]),
            (Chip.TO_CHECK, ["5.jpg"]),
            (Chip.READY, ["6.jpg"]),
        ],
    )
    def test_filters(self, chip, names):
        assert [x.name for x in self.make().filtered(chip)] == names

    def test_labels_are_in_portuguese(self):
        assert [c.label for c in Chip] == ["Todas", "Atenção", "Sem data", "A conferir", "Prontas"]


class TestDates:
    def test_batch_dates_are_unique_and_in_order(self):
        b = batch(p("a.jpg", 1, D15), p("b.jpg", 2, D13), p("c.jpg", 3, system_date=D14), p("d.jpg", 4, D15))
        assert b.batch_dates() == [D13, D14, D15]

    def test_discarded_photos_do_not_count(self):
        b = batch(p("a.jpg", 1, D15, discarded=True), p("b.jpg", 2, D13))
        assert b.batch_dates() == [D13]

    def test_apply_date_skips_photos_with_a_system_date(self):
        b = batch(p("a.jpg", 1), p("b.jpg", 2, system_date=D13), p("c.jpg", 3, D15, confirmed=True))
        assert b.apply_date(["a.jpg", "b.jpg", "c.jpg"], D14) == 2
        assert [b.photo(n).date for n in ("a.jpg", "b.jpg", "c.jpg")] == [D14, D13, D14]
        assert not b.photo("c.jpg").confirmed

    def test_apply_date_skips_discarded_photos(self):
        b = batch(p("a.jpg", 1, discarded=True))
        assert b.apply_date(["a.jpg"], D14) == 0


class TestConfirm:
    def test_confirms_a_complete_photo(self):
        b = batch(p("a.jpg", 1, D14))
        b.confirm("a.jpg")
        assert b.status("a.jpg") is Status.READY

    @pytest.mark.parametrize("photo, field", [(p("a.jpg", None, D14), "nfe"), (p("a.jpg", 1), "date")])
    def test_a_missing_field_is_reported(self, photo, field):
        b = batch(photo)
        with pytest.raises(MissingField) as error:
            b.confirm("a.jpg")
        assert error.value.field == field and not b.photo("a.jpg").confirmed

    def test_a_duplicate_cannot_be_confirmed_until_resolved(self):
        b = batch(p("a.jpg", 1, D14), p("b.jpg", 1, D14))
        with pytest.raises(DuplicateUnresolved):
            b.confirm("a.jpg")
        b.discard("b.jpg")
        assert b.status("a.jpg") is Status.TO_CHECK
        b.confirm("a.jpg")
        assert b.status("a.jpg") is Status.READY

    def test_a_confirmation_given_before_the_duplicate_appeared_is_kept(self):
        b = batch(p("a.jpg", 1, D14, confirmed=True))
        b.add(p("b.jpg", 1, D14))
        b.discard("b.jpg")
        assert b.status("a.jpg") is Status.READY

    def test_confirm_many_skips_duplicates(self):
        b = batch(p("a.jpg", 1, D14), p("b.jpg", 1, D14), p("c.jpg", 2, D14))
        assert b.confirm_many(["a.jpg", "b.jpg", "c.jpg"]) == 1
        assert [b.photo(n).confirmed for n in ("a.jpg", "b.jpg", "c.jpg")] == [False, False, True]

    def test_confirm_many_counts_only_the_photos_it_changed(self):
        ready = [p(f"r{i}.jpg", 10 + i, D14, confirmed=True) for i in range(8)]
        b = batch(*ready, p("a.jpg", 1, D14), p("b.jpg", 2, D14))
        assert b.confirm_many([x.name for x in b.visible()]) == 2

    def test_confirm_many_confirms_only_the_complete_ones(self):
        b = batch(p("a.jpg", 1, D14), p("b.jpg", 2), p("c.jpg", None, D14), p("d.jpg", 4, system_date=D13))
        assert b.confirm_many(["a.jpg", "b.jpg", "c.jpg", "d.jpg"]) == 2
        assert [b.photo(n).confirmed for n in ("a.jpg", "b.jpg", "c.jpg", "d.jpg")] == [True, False, False, True]


class TestNextPending:
    def make(self) -> Batch:
        return batch(p("a.jpg", 1, D14), p("b.jpg", 2, D14, confirmed=True), p("c.jpg", 3, D14, discarded=True),
                     p("d.jpg", 4), p("e.jpg", 5, D14, confirmed=True))

    def test_skips_ready_and_discarded_photos(self):
        assert self.make().next_pending("a.jpg") == "d.jpg"

    def test_wraps_around(self):
        assert self.make().next_pending("d.jpg") == "a.jpg"

    def test_after_discarding_the_current_photo_it_goes_on_from_there(self):
        b = batch(p("a.jpg", 1), p("b.jpg", 2), p("c.jpg", 3), p("d.jpg", 4))
        b.discard("c.jpg")
        assert b.next_pending("c.jpg") == "d.jpg"

    def test_after_keeping_a_duplicate_it_goes_on_from_the_discarded_one(self):
        b = batch(p("a.jpg", 9), p("b.jpg", 1), p("c.jpg", 1), p("d.jpg", 4))
        b.keep("b.jpg", "c.jpg")
        assert b.next_pending("c.jpg") == "d.jpg"

    def test_from_no_selection_starts_at_the_top(self):
        assert self.make().next_pending(None) == "a.jpg"

    def test_the_current_photo_counts_when_it_is_the_only_one_left(self):
        b = self.make()
        b.confirm("a.jpg")
        b.photo("d.jpg").set_typed_date(D14)
        b.confirm("d.jpg")
        assert b.next_pending("d.jpg") is None
        b.photo("d.jpg").set_typed_date(D15)
        assert b.next_pending("d.jpg") == "d.jpg"


class TestResolveDuplicates:
    def test_keep_discards_the_other_and_takes_its_date(self):
        b = batch(p("a.jpg", 1), p("b.jpg", 1, D14))
        b.keep("a.jpg", "b.jpg")
        assert b.photo("b.jpg").discarded and b.photo("a.jpg").date == D14
        assert b.status("a.jpg") is Status.TO_CHECK

    def test_the_kept_photo_must_be_confirmed_again(self):
        b = batch(p("a.jpg", 1, D14, confirmed=True), p("b.jpg", 1, D14, confirmed=True))
        b.keep("a.jpg", "b.jpg")
        assert b.status("a.jpg") is Status.TO_CHECK

    def test_keep_does_not_overwrite_a_date_already_set(self):
        b = batch(p("a.jpg", 1, D13), p("b.jpg", 1, D14))
        b.keep("a.jpg", "b.jpg")
        assert b.photo("a.jpg").date == D13

    def test_keep_takes_the_portal_lookup_of_the_other_when_it_has_none(self):
        b = batch(p("a.jpg", 1), p("b.jpg", 1, system_date=D13))
        b.keep("a.jpg", "b.jpg")
        assert b.photo("a.jpg").date == D13 and b.photo("a.jpg").date_locked

    def test_keep_does_not_replace_its_own_portal_lookup(self):
        b = batch(p("a.jpg", 1, system_date=D14), p("b.jpg", 1, system_date=D13))
        b.keep("a.jpg", "b.jpg")
        assert b.photo("a.jpg").date == D14

    def test_keep_does_not_touch_a_system_date(self):
        b = batch(p("a.jpg", 1, system_date=D13), p("b.jpg", 1, D14))
        b.keep("a.jpg", "b.jpg")
        assert b.photo("a.jpg").date == D13

    def test_wrong_number_clears_only_that_photo(self):
        b = batch(p("a.jpg", 1, D14), p("b.jpg", 1, D14))
        b.wrong_number("b.jpg")
        assert b.photo("a.jpg").nfe == 1 and b.status("b.jpg") is Status.UNREAD
        assert b.duplicates() == {}


def test_summary_of_ready_photos():
    b = batch(p("a.jpg", 1, D15, confirmed=True), p("b.jpg", 2, D14, confirmed=True),
              p("c.jpg", 3, D15, confirmed=True), p("d.jpg", 4), p("e.jpg", 5, discarded=True))
    summary = b.summary()
    assert (summary.ready, summary.ready_dates, summary.pending) == (3, [D14, D15], 1)
