from datetime import datetime

import pytest

from image_pipeline.filename_hint import FilenameHint, hint_from_filename


class TestWhatsApp:
    def test_reads_date_and_time(self):
        hint = hint_from_filename("WhatsApp Image 2026-11-14 at 18.42.07.jpeg")
        assert hint == FilenameHint("whatsapp", datetime(2026, 11, 14, 18, 42, 7))

    @pytest.mark.parametrize("suffix", [" (1)", " (12)"])
    def test_accepts_the_copy_counter(self, suffix):
        hint = hint_from_filename(f"WhatsApp Image 2026-11-14 at 18.42.07{suffix}.jpeg")
        assert hint == FilenameHint("whatsapp", datetime(2026, 11, 14, 18, 42, 7))

    @pytest.mark.parametrize("ext", [".jpg", ".JPEG", ".Jpg"])
    def test_accepts_jpg_and_any_case(self, ext):
        assert hint_from_filename(f"WhatsApp Image 2026-11-14 at 18.42.07{ext}") is not None

    def test_label(self):
        hint = hint_from_filename("WhatsApp Image 2026-11-14 at 18.42.07 (1).jpeg")
        assert hint.label() == "Foto recebida no WhatsApp em 14/11 às 18:42"


class TestScreenshot:
    def test_reads_date_and_time(self):
        hint = hint_from_filename("Captura de tela 2026-11-14 191530.png")
        assert hint == FilenameHint("screenshot", datetime(2026, 11, 14, 19, 15, 30))

    def test_accepts_uppercase_extension(self):
        assert hint_from_filename("Captura de tela 2026-11-14 191530.PNG") is not None

    def test_label(self):
        hint = hint_from_filename("Captura de tela 2026-01-05 090500.png")
        assert hint.label() == "Captura de tela de 05/01 às 09:05"


def test_ignores_the_directory():
    hint = hint_from_filename(r"C:\Canhotos\entrada\WhatsApp Image 2026-11-14 at 18.42.07.jpeg")
    assert hint == FilenameHint("whatsapp", datetime(2026, 11, 14, 18, 42, 7))


@pytest.mark.parametrize(
    "name",
    [
        "4406833.jpg",
        "IMG_20261114_184207.jpg",
        "",
        "WhatsApp Image 2026-11-14 at 18.42.07.png",
        "WhatsApp Image 2026-11-14 at 18.42.jpeg",
        "copia de WhatsApp Image 2026-11-14 at 18.42.07.jpeg",
        "Captura de tela 2026-11-14 191530.jpg",
    ],
)
def test_returns_none_for_other_names(name):
    assert hint_from_filename(name) is None


@pytest.mark.parametrize(
    "name",
    [
        "WhatsApp Image 2026-02-30 at 10.00.00.jpeg",
        "WhatsApp Image 2026-13-01 at 10.00.00.jpeg",
        "WhatsApp Image 2026-11-14 at 25.00.00.jpeg",
        "Captura de tela 2026-11-14 196000.png",
    ],
)
def test_returns_none_for_a_date_that_does_not_exist(name):
    assert hint_from_filename(name) is None
