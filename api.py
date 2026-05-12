from urllib.parse import urlparse

import requests

from config import LOGIN_URL, CANHOTOS_URL, HEADERS_CONSULTA


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
