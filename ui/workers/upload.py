import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

import api
from utils.status import CONNECTION_FAILED, Tone

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


class UploadWorker:
    """Uploads each renamed image whose receipt is PENDENTE. Files are only ever moved, never deleted:
    sent → ../pendentes, other status → ../nao-pendentes, anything that failed stays where it is."""

    def __init__(
        self,
        session,
        folder: str,
        batch_date: str,
        stop_event: threading.Event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
        on_session_lost: Callable,
        relogin: Callable[[], object],
        client=api,
    ):
        self._session         = session
        self._folder          = Path(folder)
        self._batch_date      = batch_date
        self._stop            = stop_event
        self._after           = after_fn
        self._on_update       = on_update
        self._on_done         = on_done
        self._on_cancel       = on_cancel
        self._on_session_lost = on_session_lost
        self._relogin         = relogin
        self._api             = client  # the api module; a fake in tests

    def run(self) -> None:
        try:
            self._upload_all()
        except api.Cancelled:
            self._after(0, self._on_cancel)
        except api.SessionLost:
            self._after(0, self._on_session_lost)
        else:
            self._after(0, self._on_done)

    def _upload_all(self) -> None:
        pending_dir     = self._folder.parent / "pendentes"
        non_pending_dir = self._folder.parent / "nao-pendentes"
        pending_dir.mkdir(exist_ok=True)
        non_pending_dir.mkdir(exist_ok=True)

        files = sorted(f for f in os.listdir(self._folder) if f.lower().endswith(_IMAGE_EXTENSIONS))
        total = len(files)
        t0 = time.time()

        for i, filename in enumerate(files):
            if self._stop.is_set():
                raise api.Cancelled()
            tone, text = self._upload_one(filename, pending_dir, non_pending_dir)
            invoice_num = Path(filename).stem
            self._after(0, self._on_update, invoice_num, tone, text, (i + 1) / total, i + 1, total, time.time() - t0)

    def _upload_one(self, filename: str, pending_dir: Path, non_pending_dir: Path) -> tuple[Tone, str]:
        """Tone and text for one file. Cancel and session loss propagate and stop the batch."""
        invoice_num = Path(filename).stem
        path        = self._folder / filename

        def call(fn: Callable):
            return api.call_with_relogin(fn, self._relogin)

        try:
            oid, api_status = call(
                lambda: self._api.get_invoice_for_upload(self._session, invoice_num, stop=self._stop),
            )
            if oid is None:
                return Tone.ERROR, api_status
            if api_status != "PENDENTE":
                shutil.move(str(path), str(non_pending_dir / filename))
                return Tone.WARNING, api_status

            full_data = call(lambda: self._api.get_invoice_details(self._session, oid, stop=self._stop))
            ok, err = call(lambda: self._api.upload_invoice(
                self._session, invoice_num, path, full_data, self._batch_date, stop=self._stop,
            ))
            if not ok:
                return Tone.ERROR, err
            shutil.move(str(path), str(pending_dir / filename))
            return Tone.OK, "Enviado"
        except (api.Cancelled, api.SessionLost):
            raise
        except api.ConnectionFailed:
            return Tone.CONNECTION, CONNECTION_FAILED
        except Exception as e:
            return Tone.ERROR, api.friendly_error(e)
