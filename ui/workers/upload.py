import os
import shutil
import time
from pathlib import Path
from typing import Callable

import api


class UploadWorker:
    def __init__(
        self,
        session,
        pasta: str,
        data_lote: str,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._session   = session
        self._pasta     = pasta
        self._data_lote = data_lote
        self._stop      = stop_event
        self._after     = after_fn
        self._on_update = on_update
        self._on_done   = on_done
        self._on_cancel = on_cancel

    def run(self) -> None:
        pasta        = self._pasta
        pendente_dir = Path(pasta).parent / "pendentes"
        nao_pend_dir = Path(pasta).parent / "nao_pendentes"
        pendente_dir.mkdir(exist_ok=True)
        nao_pend_dir.mkdir(exist_ok=True)

        files = [f for f in os.listdir(pasta) if f.lower().endswith(".jpg")]
        total = len(files)
        t0 = time.time()

        for i, arquivo in enumerate(files):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            nfe  = Path(arquivo).stem
            path = Path(pasta) / arquivo

            try:
                oid, status_api = api.consultar_canhoto_upload(self._session, nfe)
                if oid is None:
                    status = "❌ Não encontrada"
                elif status_api != "PENDENTE":
                    shutil.move(str(path), str(nao_pend_dir / arquivo))
                    status = f"⚠ {status_api}"
                else:
                    full_data = api.get_canhoto_completo(self._session, oid)
                    ok, err = api.upload_canhoto(self._session, nfe, path, full_data, self._data_lote)
                    if ok:
                        shutil.move(str(path), str(pendente_dir / arquivo))
                        status = "✅ Enviado"
                    else:
                        status = f"❌ {err}"
            except Exception as e:
                status = f"❌ {api.erro_amigavel(e)}"

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, nfe, status, prog, i + 1, total, elapsed)

        self._after(0, self._on_done)
