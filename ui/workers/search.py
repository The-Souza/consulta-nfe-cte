import time
from typing import Callable

import api


class SearchWorker:
    def __init__(
        self,
        session,
        start: int,
        end: int,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._session    = session
        self._start      = start
        self._end        = end
        self._stop       = stop_event
        self._after      = after_fn
        self._on_update  = on_update
        self._on_done    = on_done
        self._on_cancel  = on_cancel

    def run(self) -> None:
        start, end = self._start, self._end
        total = end - start + 1
        t0 = time.time()

        for i, invoice_num in enumerate(range(start, end + 1)):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            try:
                cte, status, has_image = api.get_invoice(self._session, invoice_num)
            except Exception as e:
                cte, status, has_image = "-", f"❌ {api.friendly_error(e)}", "-"

            r = {"NF-e": invoice_num, "CT-e": cte, "Imagem": has_image, "Status": status}
            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, r, prog, i + 1, total, elapsed)
            time.sleep(0.05)

        self._after(0, self._on_done)
