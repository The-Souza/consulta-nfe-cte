import pandas as pd

from utils.search_results import cte_counts

_SUMMARY_COLUMNS = ["CT-e", "NF-es"]


def format_image(value) -> str:
    if value in ("Sim", "Não"):
        return value
    return "-"


def build_rows(results: list[dict]) -> list[dict]:
    return [
        {"NF-e": r["NF-e"], "CT-e": r["CT-e"], "Imagem": format_image(r.get("Imagem")), "Status": r["Status"]}
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
