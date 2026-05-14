import base64
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import LOGIN_URL, CANHOTOS_URL, HEADERS_CONSULTA


def erro_amigavel(e: Exception) -> str:
    if isinstance(e, requests.exceptions.ConnectionError):
        return "Sem conexão com o servidor"
    if isinstance(e, requests.exceptions.Timeout):
        return "Tempo de resposta esgotado"
    return str(e)[:80]


def fazer_login(session: requests.Session, email: str, senha: str) -> str:
    """POST de login. Injeta o auth-token na sessão e retorna o nome do usuário."""
    domain = urlparse(LOGIN_URL).netloc
    resp = session.post(
        LOGIN_URL,
        json={"email": email, "senha": senha, "url": f"https://{domain}/"},
        timeout=10,
    )
    if not resp.ok:
        raise ValueError("E-mail ou senha inválidos.")
    data  = resp.json()
    token = data.get("id")
    if not token:
        raise ValueError("Resposta inesperada do servidor.")
    session.cookies.set("auth-token", token, domain=domain)
    return data.get("usuario", {}).get("nome", "")


def consultar_canhoto(session: requests.Session, nfe: int) -> tuple[str, str]:
    """GET de um canhoto. Retorna (numero_cte, status_label)."""
    resp = session.get(
        CANHOTOS_URL,
        headers=HEADERS_CONSULTA,
        params={"limit": 40, "numero": nfe, "offset": 0},
        timeout=10,
    )
    data = resp.json()
    if not data.get("data"):
        return "-", "❌ Não cadastrada"
    cte = data["data"][0].get("numeroCte")
    if cte:
        return str(cte), "✅ OK"
    return "-", "⚠ Sem CT-e"


def consultar_canhoto_upload(session: requests.Session, nfe: str) -> tuple[str | None, str]:
    """GET de um canhoto para upload. Retorna (oid, status_api) ou (None, status_label)."""
    resp = session.get(
        CANHOTOS_URL,
        headers=HEADERS_CONSULTA,
        params={
            "canhotoComImagemInvalidada": "false",
            "canhotoSemCte": "false",
            "canhotoSemDataEntrega": "false",
            "canhotoSemImagem": "false",
            "limit": 40,
            "numero": nfe,
            "offset": 0,
        },
        timeout=10,
    )
    data = resp.json()
    if not data.get("data"):
        return None, "❌ Não encontrada"
    item = data["data"][0]
    return item.get("oid"), item.get("status", "")


def get_canhoto_completo(session: requests.Session, oid: str) -> dict:
    """GET dados completos de um canhoto pelo oid."""
    headers = {**HEADERS_CONSULTA, "programa": "Canhoto"}
    resp = session.get(f"{CANHOTOS_URL}/{oid}", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def upload_canhoto(
    session: requests.Session,
    nfe: str,
    file_path: Path,
    full_data: dict,
    data_lote: str,
) -> tuple[bool, str | None]:
    """POST upload de imagem de canhoto. Retorna (sucesso, mensagem_erro)."""
    with open(file_path, "rb") as f:
        base64_img = base64.b64encode(f.read()).decode()

    if not full_data.get("documentoIndustria", {}).get("dataEntrega"):
        full_data["documentoIndustria"]["dataEntrega"] = data_lote

    payload = {
        **full_data,
        "base64": base64_img,
        "nomeImagem": f"{nfe}.jpeg",
        "dataEntregaAlterada": True,
        "validaDataEntrega": True,
    }
    headers = {**HEADERS_CONSULTA, "programa": "Canhoto"}
    resp = session.post(f"{CANHOTOS_URL}/salvar", headers=headers, json=payload, timeout=30)
    if not resp.ok:
        return False, resp.text[:200]
    return True, None
