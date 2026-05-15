import time
from typing import Callable

import api


class BuscaWorker:
    def __init__(
        self,
        session,
        inicio: int,
        fim: int,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._session = session
        self._inicio  = inicio
        self._fim     = fim
        self._stop    = stop_event
        self._after   = after_fn
        self._on_update  = on_update
        self._on_done    = on_done
        self._on_cancel  = on_cancel

    def run(self) -> None:
        inicio, fim = self._inicio, self._fim
        total = fim - inicio + 1
        t0 = time.time()

        for i, nfe in enumerate(range(inicio, fim + 1)):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            try:
                cte, status = api.consultar_canhoto(self._session, nfe)
            except Exception as e:
                cte, status = "-", f"❌ {api.erro_amigavel(e)}"

            r = {"NF-e": nfe, "CT-e": cte, "Status": status}
            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, r, prog, i + 1, total, elapsed)
            time.sleep(0.05)

        self._after(0, self._on_done)
