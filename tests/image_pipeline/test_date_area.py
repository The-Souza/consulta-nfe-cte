import numpy as np
import pytesseract
import pytest

from image_pipeline import date_area as module
from image_pipeline.date_area import date_area

AREA_W, AREA_H = 1200, 216


def make_area() -> np.ndarray:
    """A receipt area whose columns are all different, so a crop can be told apart by its pixels."""
    cols = (np.arange(AREA_W) % 251).astype(np.uint8)
    return np.repeat(np.tile(cols, (AREA_H, 1))[:, :, None], 3, axis=2)


class FakeTesseract:
    """Stands in for pytesseract.image_to_data: returns the given words at area positions, scaled to the
    upscaled image it receives."""

    def __init__(self, words: dict[str, int], error: Exception | None = None):
        self.words, self.error, self.calls = words, error, 0

    def __call__(self, image, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        scale = image.shape[1] / AREA_W
        return {"text": list(self.words), "left": [round(x * scale) for x in self.words.values()]}


@pytest.fixture
def tesseract(monkeypatch):
    def install(words: dict[str, int], error: Exception | None = None) -> FakeTesseract:
        fake = FakeTesseract(words, error)
        monkeypatch.setattr(module.pytesseract, "image_to_data", fake)
        return fake

    return install


def assert_crop(result, start: int, end: int):
    area = make_area()
    assert result.anchored
    assert result.image.shape == (AREA_H, end - start, 3)
    assert np.array_equal(result.image, area[:, start:end])


class TestAnchored:
    def test_crops_from_data_to_identificacao(self, tesseract):
        tesseract({"DATA": 400, "IDENTIFICAÇÃO": 650})
        assert_crop(date_area(make_area()), 400 - 15, 650 - 5)

    def test_falls_back_to_recebimento_for_the_start(self, tesseract):
        tesseract({"RECEBIMENTO": 480, "IDENTIFICAÇÃO": 650})
        assert_crop(date_area(make_area()), 480 - 90, 650 - 5)

    def test_falls_back_to_identificacao_for_the_start(self, tesseract):
        tesseract({"IDENTIFICAÇÃO": 650})
        assert_crop(date_area(make_area()), 650 - 300, 650 - 5)

    def test_without_identificacao_uses_the_default_width(self, tesseract):
        tesseract({"DATA": 400})
        assert_crop(date_area(make_area()), 385, 385 + 300)

    def test_an_end_too_close_to_the_start_is_ignored(self, tesseract):
        tesseract({"DATA": 400, "IDENTIFICACAO": 420})
        assert_crop(date_area(make_area()), 385, 385 + 300)

    def test_crop_is_kept_inside_the_area(self, tesseract):
        tesseract({"DATA": 5})
        assert_crop(date_area(make_area()), 0, 5 - 15 + 300)

    def test_crop_does_not_pass_the_right_edge(self, tesseract):
        tesseract({"DATA": 1100})
        assert_crop(date_area(make_area()), 1085, AREA_W)

    @pytest.mark.parametrize("words", [{"IDENTIFICACAO": 3}, {"DATA": AREA_W + 40}])
    def test_a_crop_with_no_room_gives_the_whole_area(self, tesseract, words):
        tesseract(words)
        result = date_area(make_area())
        assert not result.anchored
        assert np.array_equal(result.image, make_area())


class TestWordMatching:
    @pytest.mark.parametrize("word", ["data", "DATA:", "Data"])
    def test_ignores_case_and_punctuation(self, tesseract, word):
        tesseract({word: 400, "IDENTIFICACAO": 650})
        assert_crop(date_area(make_area()), 385, 645)

    def test_accepts_one_wrong_letter_in_a_long_word(self, tesseract):
        tesseract({"RECEBIMENT0": 480, "IDENTIFICAÇAO": 650})
        assert_crop(date_area(make_area()), 390, 645)

    def test_recebedor_is_not_recebimento(self, tesseract):
        tesseract({"RECEBEDOR": 480})
        result = date_area(make_area())
        assert not result.anchored

    @pytest.mark.parametrize("word", ["", "DA", "  "])
    def test_ignores_empty_and_short_words(self, tesseract, word):
        tesseract({word: 400})
        assert not date_area(make_area()).anchored


class TestFallback:
    def test_no_word_gives_the_whole_area(self, tesseract):
        tesseract({"RECEBEMOS": 100, "PRODUTOS": 300})
        result = date_area(make_area())
        assert not result.anchored
        assert np.array_equal(result.image, make_area())

    @pytest.mark.parametrize(
        "error", [pytesseract.TesseractNotFoundError(), pytesseract.TesseractError(1, "failed")]
    )
    def test_tesseract_missing_or_failing_gives_the_whole_area(self, tesseract, error):
        tesseract({}, error=error)
        result = date_area(make_area())
        assert not result.anchored
        assert np.array_equal(result.image, make_area())


class TestPasses:
    def test_stops_once_both_labels_are_found(self, tesseract):
        fake = tesseract({"DATA": 400, "IDENTIFICACAO": 650})
        date_area(make_area())
        assert fake.calls == 1

    def test_tries_every_pass_when_a_label_is_missing(self, tesseract):
        fake = tesseract({"DATA": 400})
        date_area(make_area())
        assert fake.calls == 4
