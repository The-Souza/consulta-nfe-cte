import pandas as pd


def export_excel(results: list[dict]) -> str:
    start    = results[0]["NF-e"]
    end      = results[-1]["NF-e"]
    filename = f"consulta_nfe_{start}_{end}.xlsx"
    df = pd.DataFrame([
        {"NF-e": r["NF-e"], "CT-e": r["CT-e"], "Imagem": r.get("Imagem", "-"), "Status": r["Status"].split(" ", 1)[-1]}
        for r in results
    ])
    df.to_excel(filename, index=False)
    return filename
