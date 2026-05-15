import pandas as pd


def exportar_excel(resultados: list[dict]) -> str:
    inicio  = resultados[0]["NF-e"]
    fim     = resultados[-1]["NF-e"]
    arquivo = f"consulta_nfe_{inicio}_{fim}.xlsx"
    df = pd.DataFrame([
        {"NF-e": r["NF-e"], "CT-e": r["CT-e"], "Status": r["Status"].split(" ", 1)[-1]}
        for r in resultados
    ])
    df.to_excel(arquivo, index=False)
    return arquivo
