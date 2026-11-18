import pytest

from utils.excel import build_rows


def _result(status="OK", image="Sim", cte="12345"):
    return {"NF-e": 100, "CT-e": cte, "Imagem": image, "Status": status}


@pytest.mark.parametrize("status", ["OK", "Sem CT-e", "Não cadastrada", "Tempo de conexão esgotado."])
def test_build_rows_keeps_full_status_text(status):
    assert build_rows([_result(status=status)])[0]["Status"] == status


@pytest.mark.parametrize(("image", "expected"), [("Sim", "Sim"), ("Não", "Não"), ("-", "-"), (None, "-")])
def test_build_rows_formats_image(image, expected):
    assert build_rows([_result(image=image)])[0]["Imagem"] == expected


def test_build_rows_without_image_key():
    row = {"NF-e": 100, "CT-e": "-", "Status": "Não cadastrada"}

    assert build_rows([row])[0]["Imagem"] == "-"


def test_build_rows_keeps_column_order_and_values():
    rows = build_rows([_result(), _result(status="Sem CT-e", cte="-")])

    assert rows == [
        {"NF-e": 100, "CT-e": "12345", "Imagem": "Sim", "Status": "OK"},
        {"NF-e": 100, "CT-e": "-", "Imagem": "Sim", "Status": "Sem CT-e"},
    ]
    assert list(rows[0]) == ["NF-e", "CT-e", "Imagem", "Status"]
