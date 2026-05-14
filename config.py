import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Funciona tanto rodando como script quanto como .exe gerado pelo PyInstaller
_base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
load_dotenv(_base / ".env")

LOGIN_URL    = os.getenv("LOGIN_URL")
CANHOTOS_URL = os.getenv("CANHOTOS_URL")

HEADERS_CONSULTA = {
    "accept":        "application/json, text/plain, */*",
    "programa":      os.getenv("PROGRAMA"),
    "sigla-sistema": os.getenv("SIGLA_SISTEMA"),
    "user-agent":    "Mozilla/5.0",
}

APP_NAME       = os.getenv("APP_NAME", "consulta-nfe")
APP_SUBTITULO  = os.getenv("APP_SUBTITULO", "")
ICON_PATH      = _base / os.getenv("ICON_FILE", "icon.ico")
TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
