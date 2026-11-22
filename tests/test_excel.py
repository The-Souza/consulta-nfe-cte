from datetime import date

import pandas as pd
import pytest

from utils.excel import build_rows, cte_summary, export_by_driver, export_excel, sheet_name


def _result(status="OK", image="Sim", cte="12345", driver="Ana", delivered=date(2026, 11, 12)):
    return {"NF-e": 100, "CT-e": cte, "Imagem": image, "Status": status, "Motorista": driver, "Entrega": delivered}


@pytest.mark.parametrize("status", ["OK", "Sem CT-e", "Não cadastrada", "Tempo de conexão esgotado."])
def test_build_rows_keeps_full_status_text(status):
    assert build_rows([_result(status=status)])[0]["Status"] == status


@pytest.mark.parametrize(("image", "expected"), [("Sim", "Sim"), ("Não", "Não"), ("-", "-"), (None, "-")])
def test_build_rows_formats_image(image, expected):
    assert build_rows([_result(image=image)])[0]["Imagem"] == expected


def test_build_rows_without_image_key():
    row = {"NF-e": 100, "CT-e": "-", "Status": "Não cadastrada", "Motorista": "", "Entrega": None}

    assert build_rows([row])[0]["Imagem"] == "-"


def test_build_rows_keeps_column_order_and_values():
    rows = build_rows([_result(), _result(status="Sem CT-e", cte="-")])

    assert rows == [
        {"NF-e": 100, "CT-e": "12345", "Imagem": "Sim", "Motorista": "Ana", "Entrega": "12/11/2026", "Status": "OK"},
        {"NF-e": 100, "CT-e": "-", "Imagem": "Sim", "Motorista": "Ana", "Entrega": "12/11/2026", "Status": "Sem CT-e"},
    ]
    assert list(rows[0]) == ["NF-e", "CT-e", "Imagem", "Motorista", "Entrega", "Status"]


def test_build_rows_without_driver_leaves_driver_and_date_empty():
    row = build_rows([_result(driver="", delivered=None)])[0]

    assert (row["Motorista"], row["Entrega"]) == ("", "")


def test_build_rows_with_driver_but_no_date():
    assert build_rows([_result(delivered=None)])[0]["Entrega"] == ""


# cte summary ------------------------------------------------------------------------

def _invoice(nfe, cte):
    status = "OK" if cte != "-" else "Sem CT-e"
    return {"NF-e": nfe, "CT-e": cte, "Imagem": "Sim", "Status": status, "Motorista": "", "Entrega": None}


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
    assert list(sheets["Consulta"].columns) == ["NF-e", "CT-e", "Imagem", "Motorista", "Entrega", "Status"]
    assert sheets["Resumo CT-e"].values.tolist() == [["25540", "3"], ["5533", "1"]]


def test_export_without_ctes_keeps_an_empty_summary_sheet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    filename = export_excel([_invoice(7, "-")])

    sheets = pd.read_excel(tmp_path / filename, sheet_name=None)
    assert list(sheets["Resumo CT-e"].columns) == ["CT-e", "NF-es"]
    assert sheets["Resumo CT-e"].empty


# sheet names ------------------------------------------------------------------------

def test_sheet_name_keeps_a_valid_name():
    assert sheet_name("Ana Souza", set()) == "Ana Souza"


def test_sheet_name_removes_characters_excel_rejects():
    assert sheet_name("Ana/Bia\\Caio?*[Davi]:", set()) == "AnaBiaCaioDavi"


def test_sheet_name_cuts_at_31_characters():
    assert sheet_name("A" * 40, set()) == "A" * 31


def test_sheet_name_trims_spaces_left_by_the_cut():
    assert sheet_name("A" * 30 + " B", set()) == "A" * 30


@pytest.mark.parametrize("name", ["", "   ", "/?*"])
def test_sheet_name_without_a_usable_name(name):
    assert sheet_name(name, set()) == "Sem motorista"


def test_sheet_name_numbers_repeated_names():
    assert sheet_name("Ana", {"Ana"}) == "Ana (2)"
    assert sheet_name("Ana", {"Ana", "Ana (2)"}) == "Ana (3)"


def test_sheet_name_repetition_ignores_case_like_excel():
    assert sheet_name("ANA", {"Ana"}) == "ANA (2)"


def test_sheet_name_repeated_after_the_cut_stays_within_31_characters():
    name = sheet_name("A" * 40, {"A" * 31})

    assert name == "A" * 27 + " (2)"
    assert len(name) == 31


def test_sheet_name_does_not_change_the_used_names():
    used = {"Ana"}

    sheet_name("Ana", used)

    assert used == {"Ana"}


# export by driver -------------------------------------------------------------------

def _no_image(nfe, driver, delivered=None, cte="25540"):
    return {"NF-e": nfe, "CT-e": cte, "Imagem": "Não", "Status": "OK", "Motorista": driver, "Entrega": delivered}


NO_IMAGE = [
    _no_image(10, "Bia", date(2026, 11, 14)),
    _no_image(11, "", cte="-"),
    _no_image(12, "Ana", date(2026, 11, 12)),
    _no_image(13, "Bia", None, cte="5533"),
    _no_image(14, "Bia", date(2026, 11, 15)),
]


def _export(tmp_path, monkeypatch, rows):
    monkeypatch.chdir(tmp_path)
    filename = export_by_driver(rows)
    return filename, pd.read_excel(tmp_path / filename, sheet_name=None, dtype=str, keep_default_na=False)


def test_export_by_driver_names_the_file_after_the_first_and_last_invoice(tmp_path, monkeypatch):
    filename, _ = _export(tmp_path, monkeypatch, NO_IMAGE)

    assert filename == "sem_imagem_por_motorista_10_14.xlsx"


def test_export_by_driver_has_one_sheet_per_driver_in_the_panel_order(tmp_path, monkeypatch):
    _, sheets = _export(tmp_path, monkeypatch, NO_IMAGE)

    assert list(sheets) == ["Bia", "Ana", "Sem motorista"]


def test_export_by_driver_lists_driver_invoice_delivery_date_and_cte(tmp_path, monkeypatch):
    _, sheets = _export(tmp_path, monkeypatch, NO_IMAGE)

    assert list(sheets["Bia"].columns) == ["Motorista", "NF-e", "Entrega", "CT-e"]
    assert sheets["Bia"].values.tolist() == [
        ["Bia", "10", "14/11/2026", "25540"],
        ["Bia", "13", "", "5533"],
        ["Bia", "14", "15/11/2026", "25540"],
    ]


def test_export_by_driver_names_the_invoices_outside_the_sheet(tmp_path, monkeypatch):
    _, sheets = _export(tmp_path, monkeypatch, NO_IMAGE)

    assert sheets["Sem motorista"].values.tolist() == [["Sem motorista na planilha", "11", "", "-"]]


def test_export_by_driver_keeps_the_full_name_when_the_sheet_name_is_cut(tmp_path, monkeypatch):
    name = "Motorista com um nome muito comprido demais"

    _, sheets = _export(tmp_path, monkeypatch, [_no_image(1, name)])

    assert list(sheets) == [name[:31].strip()]
    assert sheets[name[:31].strip()]["Motorista"].tolist() == [name]


def test_export_by_driver_keeps_drivers_whose_names_collide_as_sheets(tmp_path, monkeypatch):
    rows = [_no_image(1, "Ana/Souza"), _no_image(2, "AnaSouza"), _no_image(3, "AnaSouza")]

    _, sheets = _export(tmp_path, monkeypatch, rows)

    assert list(sheets) == ["AnaSouza", "AnaSouza (2)"]
    assert sheets["AnaSouza"]["NF-e"].tolist() == ["2", "3"]
    assert sheets["AnaSouza (2)"]["NF-e"].tolist() == ["1"]
