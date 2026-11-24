"""Synthetic stubs and access keys for the image pipeline tests.

No real CNPJ, key or photo may be committed (public repo), so every test image is drawn here.
"""

import cv2
import numpy as np

FAKE_CNPJ = "11222333000181"

STUB_W, STUB_H = 1800, 300
PHOTO_W, PHOTO_H = 1600, 900
QR_SIZE = 220
QR_X = 1300  # left edge of the QR inside the stub, as on the real stub (right side)


def check_digit(body: str) -> int:
    total = sum(int(d) * (2 + i % 8) for i, d in enumerate(reversed(body)))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def make_key(nfe: int = 4406833, model: str = "55", code: str = "12345678") -> str:
    # cUF + AAMM + CNPJ + model + series + nNF + tpEmis + cNF
    body = "35" + "2610" + FAKE_CNPJ + model + "001" + f"{nfe:09d}" + "1" + code
    assert len(body) == 43
    return body + str(check_digit(body))


def qr_image(text: str, size: int = QR_SIZE) -> np.ndarray:
    modules = cv2.QRCodeEncoder.create().encode(text)
    return cv2.resize(modules, (size, size), interpolation=cv2.INTER_NEAREST)


def make_stub(key: str | None = None) -> np.ndarray:
    """White stub strip (BGR) with the layout boxes and, if given, the QR on the right."""
    stub = np.full((STUB_H, STUB_W, 3), 255, np.uint8)
    dark = (60, 40, 40)
    cv2.rectangle(stub, (20, 20), (STUB_W - 20, STUB_H - 20), dark, 3)
    cv2.line(stub, (20, 70), (QR_X - 20, 70), dark, 2)
    cv2.line(stub, (360, 70), (360, STUB_H - 20), dark, 2)
    cv2.line(stub, (QR_X - 20, 20), (QR_X - 20, STUB_H - 20), dark, 2)
    cv2.line(stub, (QR_X + QR_SIZE + 20, 20), (QR_X + QR_SIZE + 20, STUB_H - 20), dark, 2)
    cv2.putText(stub, "004406833", (QR_X + QR_SIZE + 40, 170), cv2.FONT_HERSHEY_SIMPLEX, 1.2, dark, 3)
    if key is not None:
        qr = cv2.cvtColor(qr_image(key), cv2.COLOR_GRAY2BGR)
        top = (STUB_H - QR_SIZE) // 2
        stub[top:top + QR_SIZE, QR_X:QR_X + QR_SIZE] = qr
    return stub


def make_photo(stub: np.ndarray, angle: float = 0.0, upside_down: bool = False, width: int = 1400) -> np.ndarray:
    """The stub scaled to `width`, centred on a darker background, then rotated."""
    scale = width / stub.shape[1]
    small = cv2.resize(stub, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    photo = np.full((PHOTO_H, PHOTO_W, 3), 90, np.uint8)
    h, w = small.shape[:2]
    top, left = (PHOTO_H - h) // 2, (PHOTO_W - w) // 2
    photo[top:top + h, left:left + w] = small
    if angle:
        matrix = cv2.getRotationMatrix2D((PHOTO_W / 2, PHOTO_H / 2), angle, 1.0)
        photo = cv2.warpAffine(photo, matrix, (PHOTO_W, PHOTO_H), borderValue=(90, 90, 90))
    if upside_down:
        photo = cv2.rotate(photo, cv2.ROTATE_180)
    return photo
