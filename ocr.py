import re

import cv2
import numpy as np
import pytesseract

from config import TESSERACT_PATH

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_OCR_CONFIGS = ["--psm 6", "--psm 11", "--psm 3"]


def _extract_nfe(text: str) -> str | None:
    text = re.sub(r"[oO]", "0", text)
    match = re.search(r"00(\d{7})(?!\d)", text)
    return match.group(1) if match else None


def _rotate(img, angle):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _preprocess_variants(img):
    _, w = img.shape[:2]
    right = img[:, w // 2:]
    variants = []

    for source in [img, right]:
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        sh, sw = gray.shape
        large = cv2.resize(gray, (sw * 2, sh * 2), interpolation=cv2.INTER_CUBIC)
        _, v_fixed = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        _, v_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        v_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        _, v_clahe = cv2.threshold(clahe.apply(large), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        v_adapt_large = cv2.adaptiveThreshold(large, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        variants.extend([v_fixed, v_otsu, v_adapt, v_clahe, v_adapt_large])

    gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    for angle in [-5, 5, -10, 10]:
        rotated = _rotate(gray_full, angle)
        _, v_rot = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(v_rot)

    return variants


def process_image(path: str) -> str | None:
    """Extrai o número de NF-e de uma imagem via OCR. Retorna None se não encontrar."""
    # np.fromfile lida com caminhos Unicode no Windows (cv2.imread falha com acentos)
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    for variant in _preprocess_variants(img):
        for config in _OCR_CONFIGS:
            text = pytesseract.image_to_string(variant, config=config)
            nfe = _extract_nfe(text)
            if nfe:
                return nfe
    return None
