import os
import shutil
import time
from pathlib import Path
from typing import Callable

import api
from utils.status import Tone


class UploadWorker:
    def __init__(
        self,
        session,
        folder: str,
        batch_date: str,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._session    = session
        self._folder     = folder
        self._batch_date = batch_date
        self._stop       = stop_event
        self._after      = after_fn
        self._on_update  = on_update
        self._on_done    = on_done
        self._on_cancel  = on_cancel

    def run(self) -> None:
        folder          = self._folder
        pending_dir     = Path(folder).parent / "pendentes"
        non_pending_dir = Path(folder).parent / "nao-pendentes"
        pending_dir.mkdir(exist_ok=True)
        non_pending_dir.mkdir(exist_ok=True)

        files = [f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        total = len(files)
        t0 = time.time()

        for i, filename in enumerate(files):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            invoice_num = Path(filename).stem
            path        = Path(folder) / filename

            attempts = 2 if i == 0 else 1
            tone, text = Tone.ERROR, ""
            for attempt in range(attempts):
                try:
                    oid, api_status = api.get_invoice_for_upload(self._session, invoice_num, stop=self._stop)
                    if oid is None:
                        tone, text = Tone.ERROR, api_status
                    elif api_status != "PENDENTE":
                        shutil.move(str(path), str(non_pending_dir / filename))
                        tone, text = Tone.WARNING, api_status
                    else:
                        full_data = api.get_invoice_details(self._session, oid, stop=self._stop)
                        ok, err = api.upload_invoice(
                            self._session, invoice_num, path, full_data, self._batch_date, stop=self._stop,
                        )
                        if ok:
                            shutil.move(str(path), str(pending_dir / filename))
                            tone, text = Tone.OK, "Enviado"
                        else:
                            tone, text = Tone.ERROR, err
                    break
                except api.Cancelled:
                    self._after(0, self._on_cancel)
                    return
                except Exception as e:
                    if attempt + 1 < attempts:
                        time.sleep(0.8)
                        continue
                    tone, text = Tone.ERROR, api.friendly_error(e)

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, invoice_num, tone, text, prog, i + 1, total, elapsed)

        self._after(0, self._on_done)
