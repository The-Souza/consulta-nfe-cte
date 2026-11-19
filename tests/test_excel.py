import pandas as pd
import pytest

from utils.excel import build_rows, cte_summary, export_excel


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


# cte summary ------------------------------------------------------------------------

def _invoice(nfe, cte):
    return {"NF-e": nfe, "CT-e": cte, "Imagem": "Sim", "Status": "OK" if cte != "-" else "Sem CT-e"}


RESULTS = [_invoice(1, "25540"), _invoice(2, "5533"), _invoice(3, "25540"), _invoice(4, "-"), _invoice(5, "25540")]


def test_cte_summary_lists_ctes_by_quantity_without_missing_cte():
    assert cte_summary(RESULTS) == [{"CT-e": "25540", "NF-es": 3}, {"CT-e": "5533", "NF-es": 1}]


def test_cte_summary_without_ctes_is_empty():
    assert cte_summary([_invoice(1, "-")]) == []


# export -----------------------------------------------------------------------------

def test_export_writes_query_and_cte_summary_sheets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    filename = export_excel(RESULTS)

    assert filename == "consulta_nfe_1_5.xlsx"
    sheets = pd.read_excel(tmp_path / filename, sheet_name=None, dtype=str)
    assert list(sheets) == ["Consulta", "Resumo CT-e"]
    assert sheets["Consulta"]["NF-e"].tolist() == ["1", "2", "3", "4", "5"]
    assert list(sheets["Consulta"].columns) == ["NF-e", "CT-e", "Imagem", "Status"]
    assert sheets["Resumo CT-e"].values.tolist() == [["25540", "3"], ["5533", "1"]]


def test_export_without_ctes_keeps_an_empty_summary_sheet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    filename = export_excel([_invoice(7, "-")])

    sheets = pd.read_excel(tmp_path / filename, sheet_name=None)
    assert list(sheets["Resumo CT-e"].columns) == ["CT-e", "NF-es"]
    assert sheets["Resumo CT-e"].empty
