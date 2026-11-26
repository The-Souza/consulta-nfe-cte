from datetime import date

import pytest

from conference.batch import Summary
from conference.labels import send_label, summary_parts

NOV_14, NOV_15, NOV_16, NOV_17, NOV_18 = (date(2026, 11, d) for d in range(14, 19))


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


class TestSendLabel:
    @pytest.mark.parametrize(("ready", "label"), [
        (0, "Enviar canhotos"),
        (1, "Enviar 1 canhoto"),
        (12, "Enviar 12 canhotos"),
    ])
    def test_the_button_counts_the_ready_photos(self, ready, label):
        assert send_label(ready) == label
