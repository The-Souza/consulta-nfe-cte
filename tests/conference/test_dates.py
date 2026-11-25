from datetime import date

import pytest

from conference.dates import DateError, full, mask, parse_date, short

TODAY = date(2026, 11, 25)


class TestParse:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("14/11/2026", date(2026, 11, 14)),
            ("4/10/2026", date(2026, 10, 4)),
            ("14/11/26", date(2026, 11, 14)),
            ("14/11", date(2026, 11, 14)),
            ("25/11", TODAY),
            (" 14/11/2026 ", date(2026, 11, 14)),
        ],
    )
    def test_reads_slashed_dates(self, text, expected):
        assert parse_date(text, TODAY) == expected

    @pytest.mark.parametrize(
        "text, expected",
        [("14112026", date(2026, 11, 14)), ("141126", date(2026, 11, 14)), ("1411", date(2026, 11, 14))],
    )
    def test_reads_digits_only(self, text, expected):
        assert parse_date(text, TODAY) == expected

    def test_empty_means_no_date(self):
        assert parse_date("", TODAY) is None
        assert parse_date("   ", TODAY) is None

    def test_without_year_a_future_date_falls_back_to_last_year(self):
        assert parse_date("20/12", date(2027, 1, 5)) == date(2026, 12, 20)

    def test_without_year_a_date_that_is_future_now_and_too_old_last_year_is_future(self):
        with pytest.raises(DateError, match="Data no futuro"):
            parse_date("26/11", TODAY)

    @pytest.mark.parametrize("text", ["14/11/2016", "14/11/16", "14/12/25", "24/05/2026"])
    def test_rejects_a_date_older_than_six_months(self, text):
        with pytest.raises(DateError, match="Data muito antiga"):
            parse_date(text, TODAY)

    def test_accepts_a_date_up_to_six_months_old(self):
        assert parse_date("26/05/2026", TODAY) == date(2026, 5, 26)
        assert parse_date("01/10", TODAY) == date(2026, 10, 1)

    @pytest.mark.parametrize("text", ["31/02/2026", "30/13/2026", "00/11/2026", "31/04", "29/02/2026"])
    def test_rejects_a_date_that_does_not_exist(self, text):
        with pytest.raises(DateError, match="Data inválida"):
            parse_date(text, TODAY)

    @pytest.mark.parametrize("text", ["26/11/2026", "01/01/2027", "26/11/26"])
    def test_rejects_a_future_date_with_a_year(self, text):
        with pytest.raises(DateError, match="Data no futuro"):
            parse_date(text, TODAY)

    @pytest.mark.parametrize("text", ["amanhã", "14-11-2026", "14/11/2026/1", "141", "1411202", "14//11", "1/2/3"])
    def test_rejects_anything_else(self, text):
        with pytest.raises(DateError, match="Data inválida"):
            parse_date(text, TODAY)


class TestMask:
    @pytest.mark.parametrize(
        "typed, shown",
        [
            ("", ""),
            ("1", "1"),
            ("14", "14"),
            ("141", "14/1"),
            ("1411", "14/11"),
            ("14112", "14/11/2"),
            ("14112026", "14/11/2026"),
            ("141120269", "14/11/2026"),
        ],
    )
    def test_adds_the_slashes_while_typing_digits(self, typed, shown):
        assert mask(typed) == shown

    def test_keeps_slashes_the_user_typed(self):
        assert mask("4/1/2026") == "4/1/2026"

    @staticmethod
    def type_keys(keys: str) -> str:
        """The field after each keystroke goes through the mask, as the screen does."""
        text = ""
        for key in keys:
            text = mask(text + key)
        return text

    @pytest.mark.parametrize(
        "keys, shown",
        [("14112026", "14/11/2026"), ("141126", "14/11/26"), ("1411", "14/11"), ("14/11/2026", "14/11/2026"),
         ("4/1/2026", "4/1/2026"), ("14/1/2026", "14/1/2026")],
    )
    def test_typing_key_by_key(self, keys, shown):
        assert self.type_keys(keys) == shown

    @pytest.mark.parametrize("edited, shown", [("1411/2026", "14/11/2026"), ("14/112026", "14/11/2026")])
    def test_deleting_a_slash_in_the_middle_puts_it_back(self, edited, shown):
        assert mask(edited) == shown

    def test_a_full_date_typed_key_by_key_is_read(self):
        assert parse_date(self.type_keys("14112026"), TODAY) == date(2026, 11, 14)

    def test_drops_letters_and_limits_the_length(self):
        assert mask("14a11") == "14/11"
        assert mask("14/11/20261") == "14/11/2026"


def test_short_and_full():
    assert short(date(2026, 1, 4)) == "04/01"
    assert full(date(2026, 1, 4)) == "04/01/2026"
