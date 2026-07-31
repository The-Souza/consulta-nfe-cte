import base64
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import LOGIN_URL, CANHOTOS_URL, QUERY_HEADERS

# The first request after opening the app is often much slower than the
# server's usual response time (cold connection), so query timeouts are
# generous to avoid false "Tempo de resposta esgotado" errors.
QUERY_TIMEOUT = 30
UPLOAD_TIMEOUT = 45


def friendly_error(e: Exception) -> str:
    if isinstance(e, requests.exceptions.ConnectionError):
        return "Sem conexão com o servidor"
    if isinstance(e, requests.exceptions.Timeout):
        return "Tempo de resposta esgotado"
    return str(e)[:80]


def login(session: requests.Session, email: str, password: str) -> str:
    """POST login. Injects auth-token into the session and returns the user name."""
    domain = urlparse(LOGIN_URL).netloc
    resp = session.post(
        LOGIN_URL,
        json={"email": email, "senha": password, "url": f"https://{domain}/"},
        timeout=QUERY_TIMEOUT,
    )
    if not resp.ok:
        raise ValueError("E-mail ou senha inválidos.")
    data  = resp.json()
    token = data.get("id")
    if not token:
        raise ValueError("Resposta inesperada do servidor.")
    session.cookies.set("auth-token", token, domain=domain)
    return data.get("usuario", {}).get("nome", "")


def get_invoice(session: requests.Session, invoice_num: int) -> tuple[str, str, str]:
    """GET invoice by number. Returns (cte_number, status_label, has_image)."""
    for attempt in range(2):
        resp = session.get(
            CANHOTOS_URL,
            headers=QUERY_HEADERS,
            params={"limit": 40, "numero": invoice_num, "offset": 0},
            timeout=QUERY_TIMEOUT,
        )
        data = resp.json()
        if data.get("data"):
            item = data["data"][0]
            cte = item.get("numeroCte")
            has_image = item.get("possuiImagem", "-")
            if cte:
                return str(cte), "✅ OK", has_image
            return "-", "⚠ Sem CT-e", has_image
        if attempt == 0:
            time.sleep(0.5)
    return "-", "❌ Não cadastrada", "-"


def get_invoice_for_upload(session: requests.Session, invoice_num: str) -> tuple[str | None, str]:
    """GET invoice for upload. Returns (oid, api_status) or (None, error_label)."""
    resp = session.get(
        CANHOTOS_URL,
        headers=QUERY_HEADERS,
        params={
            "canhotoComImagemInvalidada": "false",
            "canhotoSemCte": "false",
            "canhotoSemDataEntrega": "false",
            "canhotoSemImagem": "false",
            "limit": 40,
            "numero": invoice_num,
            "offset": 0,
        },
        timeout=QUERY_TIMEOUT,
    )
    data = resp.json()
    if not data.get("data"):
        return None, "❌ Não encontrada"
    item = data["data"][0]
    return item.get("oid"), item.get("status", "")


def get_invoice_details(session: requests.Session, oid: str) -> dict:
    """GET full invoice record by oid."""
    headers = {**QUERY_HEADERS, "programa": "Canhoto"}
    resp = session.get(f"{CANHOTOS_URL}/{oid}", headers=headers, timeout=QUERY_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def upload_invoice(
    session: requests.Session,
    invoice_num: str,
    file_path: Path,
    full_data: dict,
    batch_date: str,
) -> tuple[bool, str | None]:
    """POST invoice image upload. Returns (success, error_message)."""
    with open(file_path, "rb") as f:
        base64_img = base64.b64encode(f.read()).decode()

    if not full_data.get("documentoIndustria", {}).get("dataEntrega"):
        full_data["documentoIndustria"]["dataEntrega"] = batch_date

    payload = {
        **full_data,
        "base64": base64_img,
        "nomeImagem": f"{invoice_num}.jpeg",
        "dataEntregaAlterada": True,
        "validaDataEntrega": True,
    }
    headers = {**QUERY_HEADERS, "programa": "Canhoto"}
    resp = session.post(f"{CANHOTOS_URL}/salvar", headers=headers, json=payload, timeout=UPLOAD_TIMEOUT)
    if not resp.ok:
        return False, resp.text[:200]
    return True, None
