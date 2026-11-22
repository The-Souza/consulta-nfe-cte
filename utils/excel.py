import re

import pandas as pd

from utils.search_results import NO_DRIVER, NO_DRIVER_LABEL, cte_counts, driver_groups

_SUMMARY_COLUMNS = ["CT-e", "NF-es"]
_BY_DRIVER_COLUMNS = ["Motorista", "NF-e", "Entrega", "CT-e"]

_SHEET_NAME_MAX = 31
_SHEET_NAME_INVALID = re.compile(r"[/\\?*\[\]:]")
_NO_DRIVER_SHEET = "Sem motorista"


def format_image(value) -> str:
    if value in ("Sim", "Não"):
        return value
    return "-"


def _format_date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def build_rows(results: list[dict]) -> list[dict]:
    return [
        {
            "NF-e": r["NF-e"],
            "CT-e": r["CT-e"],
            "Imagem": format_image(r.get("Imagem")),
            "Motorista": r["Motorista"],
            "Entrega": _format_date(r["Entrega"]),
            "Status": r["Status"],
        }
        for r in results
    ]


def cte_summary(results: list[dict]) -> list[dict]:
    """One line per CT-e with how many invoices it groups, in the side panel order."""
    return [{"CT-e": cte, "NF-es": count} for cte, count in cte_counts(results)]


def export_excel(results: list[dict]) -> str:
    start    = results[0]["NF-e"]
    end      = results[-1]["NF-e"]
    filename = f"consulta_nfe_{start}_{end}.xlsx"
    with pd.ExcelWriter(filename) as writer:
        pd.DataFrame(build_rows(results)).to_excel(writer, sheet_name="Consulta", index=False)
        pd.DataFrame(cte_summary(results), columns=_SUMMARY_COLUMNS).to_excel(
            writer, sheet_name="Resumo CT-e", index=False,
        )
    return filename


def sheet_name(name: str, used: set[str]) -> str:
    """A sheet name Excel accepts for this driver, not taken by any name in `used`. Excel compares
    sheet names ignoring case."""
    base = _SHEET_NAME_INVALID.sub("", name)[:_SHEET_NAME_MAX].strip() or _NO_DRIVER_SHEET
    taken = {u.casefold() for u in used}
    candidate, n = base, 1
    while candidate.casefold() in taken:
        n += 1
        suffix = f" ({n})"
        candidate = base[:_SHEET_NAME_MAX - len(suffix)].rstrip() + suffix
    return candidate


def export_by_driver(results: list[dict]) -> str:
    """One sheet per driver, in the side panel order, to know whom to ask for the missing photos."""
    start    = results[0]["NF-e"]
    end      = results[-1]["NF-e"]
    filename = f"sem_imagem_por_motorista_{start}_{end}.xlsx"
    used: set[str] = set()
    with pd.ExcelWriter(filename) as writer:
        for group in driver_groups(results):
            # The full name on every line: the sheet name may be cut, and the rows may be copied elsewhere
            driver = NO_DRIVER_LABEL if group.driver == NO_DRIVER else group.driver
            rows = [
                {"Motorista": driver, "NF-e": r["NF-e"], "Entrega": _format_date(r["Entrega"]), "CT-e": r["CT-e"]}
                for r in results if r["Motorista"] == group.driver
            ]
            name = sheet_name(group.driver, used)
            used.add(name)
            pd.DataFrame(rows, columns=_BY_DRIVER_COLUMNS).to_excel(writer, sheet_name=name, index=False)
    return filename
