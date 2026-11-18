import pandas as pd


def format_image(value) -> str:
    if value in ("Sim", "Não"):
        return value
    return "-"


def build_rows(results: list[dict]) -> list[dict]:
    return [
        {"NF-e": r["NF-e"], "CT-e": r["CT-e"], "Imagem": format_image(r.get("Imagem")), "Status": r["Status"]}
        for r in results
    ]


def export_excel(results: list[dict]) -> str:
    start    = results[0]["NF-e"]
    end      = results[-1]["NF-e"]
    filename = f"consulta_nfe_{start}_{end}.xlsx"
    pd.DataFrame(build_rows(results)).to_excel(filename, index=False)
    return filename
