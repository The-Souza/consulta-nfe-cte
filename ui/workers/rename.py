import os
import shutil
import time
from pathlib import Path
from typing import Callable

import ocr


class RenameWorker:
    def __init__(
        self,
        folder: str,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._folder     = folder
        self._stop       = stop_event
        self._after      = after_fn
        self._on_update  = on_update
        self._on_done    = on_done
        self._on_cancel  = on_cancel

    def run(self) -> None:
        folder = self._folder
        output = Path(folder) / "renomeadas"
        output.mkdir(exist_ok=True)

        files = [f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        total = len(files)
        t0 = time.time()

        for i, filename in enumerate(files):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            path        = os.path.join(folder, filename)
            invoice_num = None
            status      = "erro"
            try:
                invoice_num = ocr.process_image(path)
                if invoice_num is None:
                    status = "nao_encontrada"
                else:
                    new_path = output / f"{invoice_num}.jpg"
                    if new_path.exists():
                        status = "duplicata"
                    else:
                        shutil.move(str(path), str(new_path))
                        status = "ok"
            except Exception:
                status = "erro"

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, filename, invoice_num, status, prog, i + 1, total, elapsed)

        self._after(0, self._on_done, str(output))
