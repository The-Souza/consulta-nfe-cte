"""Write the strip, receipt area and date box of each stub photo, for checking the crops by eye.

Dev-only script. The output holds third-party data (names, signatures), so keep it outside git: the
default folder is docs/imgs-test/recortes/. Only the source, rotation, sharpness and whether the date
box was anchored are printed, never the invoice number.

Usage: .venv\\Scripts\\python.exe tools\\dump_crops.py [photos folder] [output folder]
"""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from image_pipeline import process  # noqa: E402
from image_pipeline.date_area import date_area  # noqa: E402

DEFAULT_PHOTOS = Path("docs/imgs-test")
EXTENSIONS = {".jpg", ".jpeg", ".png"}


def save(path: Path, img: np.ndarray) -> None:
    cv2.imencode(".jpg", img)[1].tofile(str(path))


def main(photos: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted(p for p in photos.iterdir() if p.suffix.lower() in EXTENSIONS)
    for index, path in enumerate(paths, start=1):
        result = process(path)
        stem = f"{index:02d}"
        line = f"{stem}  origem={result.nfe_source or '-':3}  giro={result.rotation:3}  nitidez={result.sharpness:7.1f}"
        if result.error:
            print(f"{line}  erro: {result.error}")
            continue
        save(output / f"{stem}__foto.jpg", result.upright)
        if result.strip is not None:
            save(output / f"{stem}__tira.jpg", result.strip)
            save(output / f"{stem}__recebimento.jpg", result.receipt_area)
            date = date_area(result.receipt_area)
            save(output / f"{stem}__data.jpg", date.image)
            line += f"  data={'achada' if date.anchored else 'área inteira'}"
        print(line)
    print(f"{len(paths)} fotos -> {output}")


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PHOTOS
    main(folder, Path(sys.argv[2]) if len(sys.argv) > 2 else folder / "recortes")
