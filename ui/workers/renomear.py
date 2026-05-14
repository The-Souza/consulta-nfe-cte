import os
import shutil
import time
from pathlib import Path
from typing import Callable

import ocr


class RenomearWorker:
    def __init__(
        self,
        pasta: str,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._pasta   = pasta
        self._stop    = stop_event
        self._after   = after_fn
        self._on_update  = on_update
        self._on_done    = on_done
        self._on_cancel  = on_cancel

    def run(self) -> None:
        pasta  = self._pasta
        output = Path(pasta) / "renamed"
        output.mkdir(exist_ok=True)

        files = [f for f in os.listdir(pasta) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        total = len(files)
        t0 = time.time()

        for i, arquivo in enumerate(files):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            path   = os.path.join(pasta, arquivo)
            nfe    = None
            status = "erro"
            try:
                nfe = ocr.process_image(path)
                if nfe is None:
                    status = "nao_encontrada"
                else:
                    novo = output / f"{nfe}.jpg"
                    if novo.exists():
                        status = "duplicata"
                    else:
                        shutil.move(str(path), str(novo))
                        status = "ok"
            except Exception:
                status = "erro"

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, arquivo, nfe, status, prog, i + 1, total, elapsed)

        self._after(0, self._on_done, str(output))
