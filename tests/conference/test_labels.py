from datetime import date, datetime

import pytest

from conference.batch import Chip, Summary
from conference.labels import chip_tone, row_values, selection_label, send_label, status_tone, summary_parts
from conference.photo import Photo, Status, SystemInfo
from utils.status import Tone

NOV_14, NOV_15, NOV_16, NOV_17, NOV_18 = (date(2026, 11, d) for d in range(14, 19))
LONG_NAME = "WhatsApp Image 2026-11-14 at 18.42.07 (1).jpeg"


class TestRow:
    def test_a_read_photo_shows_its_number_name_date_and_status(self):
        photo = Photo("a.jpg", "h", nfe=4406833, typed_date=NOV_14)
        assert row_values(photo, Status.TO_CHECK) == ("4406833", "a.jpg", "14/11", "A conferir")

    def test_an_unread_photo_says_so_and_has_no_date(self):
        assert row_values(Photo("a.jpg", "h"), Status.UNREAD) == ("Não lida", "a.jpg", "—", "Não lida")

    def test_the_system_date_is_shown(self):
        photo = Photo("a.jpg", "h", nfe=1, system=SystemInfo("found", NOV_15, datetime(2026, 11, 20)))
        assert row_values(photo, Status.TO_CHECK)[2] == "15/11"

    def test_a_long_name_is_cut_in_the_middle(self):
        assert row_values(Photo(LONG_NAME, "h"), Status.UNREAD)[1] == "WhatsApp Image 2026-11-1…(1).jpeg"


class TestTone:
    @pytest.mark.parametrize(("status", "tone"), [
        (Status.UNREAD, Tone.ERROR),
        (Status.DUPLICATE, Tone.ERROR),
        (Status.NO_DATE, Tone.WARNING),
        (Status.TO_CHECK, Tone.INFO),
        (Status.READY, Tone.OK),
        (Status.DISCARDED, Tone.NEUTRAL),
    ])
    def test_each_status_has_the_design_color(self, status, tone):
        assert status_tone(status) is tone


class TestSummary:
    def test_nothing_loaded_says_nothing(self):
        assert summary_parts(Summary(0, [], 0)) == ("", "")

    def test_only_pending_photos(self):
        assert summary_parts(Summary(0, [], 5)) == ("Nenhuma pronta", " · 5 pendentes ficam na lista")

    def test_one_pending_photo_is_singular(self):
        assert summary_parts(Summary(0, [], 1)) == ("Nenhuma pronta", " · 1 pendente fica na lista")

    def test_one_ready_photo_is_singular(self):
        assert summary_parts(Summary(1, [NOV_14], 0)) == ("1 pronta", " em 14/11")

    def test_ready_photos_list_their_dates(self):
        assert summary_parts(Summary(3, [NOV_14, NOV_15], 2)) == (
            "3 prontas", " em 14/11, 15/11 · 2 pendentes ficam na lista")

    def test_many_dates_are_cut_after_four(self):
        dates = [NOV_14, NOV_15, NOV_16, NOV_17, NOV_18, date(2026, 11, 19)]
        assert summary_parts(Summary(6, dates, 0)) == ("6 prontas", " em 14/11, 15/11, 16/11, 17/11 e mais 2")


class TestChipTone:
    @pytest.mark.parametrize(("chip", "tone"), [
        (Chip.ALL, None),
        (Chip.ATTENTION, Tone.ERROR),
        (Chip.NO_DATE, Tone.WARNING),
        (Chip.TO_CHECK, Tone.INFO),
        (Chip.READY, Tone.OK),
    ])
    def test_each_chip_has_the_design_dot(self, chip, tone):
        assert chip_tone(chip) is tone


@pytest.mark.parametrize(("count", "label"), [(1, "1 selecionada"), (3, "3 selecionadas")])
def test_selection_label(count, label):
    assert selection_label(count) == label


class TestSendLabel:
    @pytest.mark.parametrize(("ready", "label"), [
        (0, "Enviar canhotos"),
        (1, "Enviar 1 canhoto"),
        (12, "Enviar 12 canhotos"),
    ])
    def test_the_button_counts_the_ready_photos(self, ready, label):
        assert send_label(ready) == label
