import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

import api
import drivers
from drivers import DriverLookup
from utils.status import CONNECTION_FAILED

logger = logging.getLogger(__name__)

BRAKE_AFTER = 3      # connection failures in a row before pausing
BRAKE_SECONDS = 10
PACE_SECONDS = 0.05  # gap between invoices, to not hammer the server


@dataclass
class SearchCallbacks:
    on_row: Callable[[dict, float, int, int, float], None]  # row, progress, current, total, elapsed
    on_notice: Callable[[str], None]
    on_done: Callable[[list[int]], None]  # invoices that still failed by connection
    on_cancel: Callable[[], None]
    on_session_lost: Callable[[], None]
    on_drivers: Callable[[DriverLookup], None]  # drivers read from Supabase, before the first invoice


class SearchWorker:
    """Queries invoices one by one, pausing when the server looks unstable and retrying connection
    failures once at the end. All callbacks go through after_fn, so the UI is only touched on the
    main thread."""

    def __init__(
        self,
        session,
        invoices: list[int],
        stop_event: threading.Event,
        after_fn: Callable,
        callbacks: SearchCallbacks,
        relogin: Callable[[], object],
        get_invoice: Callable = api.get_invoice,
        warm_up: Callable = api.warm_up,
        wait: Callable[[float], None] | None = None,
        pace: float = PACE_SECONDS,
        drivers: DriverLookup | None = None,  # already read: a retry doesn't read Supabase again
        get_drivers: Callable[[list[int]], DriverLookup] = drivers.get_drivers,
    ):
        self._session     = session
        self._invoices    = invoices
        self._stop        = stop_event
        self._after       = after_fn
        self._cb          = callbacks
        self._relogin     = relogin
        self._get_invoice = get_invoice
        self._warm_up     = warm_up
        self._wait        = wait or (lambda seconds: api._wait(seconds, stop_event))
        self._pace        = pace
        self._drivers     = drivers
        self._get_drivers = get_drivers
        self._t0          = 0.0

    def run(self) -> None:
        try:
            failures = self._search()
        except api.Cancelled:
            self._after(0, self._cb.on_cancel)
        except api.SessionLost:
            self._after(0, self._cb.on_session_lost)
        else:
            self._after(0, self._cb.on_done, failures)

    def _search(self) -> list[int]:
        if not self._invoices:
            return []
        if self._drivers is None:
            self._drivers = self._get_drivers(self._invoices)
            self._after(0, self._cb.on_drivers, self._drivers)
        try:
            self._warm_up(self._session, self._invoices[0])
        except Exception:
            logger.debug("Warm-up failed", exc_info=True)

        self._t0 = time.time()
        failures = self._pass(self._invoices)
        if failures:
            self._after(0, self._cb.on_notice, f"Tentando de novo {len(failures)} NF-e(s) com falha de conexão…")
            failures = self._pass(failures)
        return failures

    def _pass(self, invoices: list[int]) -> list[int]:
        failures: list[int] = []
        streak = 0
        total = len(invoices)
        for i, invoice_num in enumerate(invoices):
            if self._stop.is_set():
                raise api.Cancelled()

            row, connection_failed = self._query(invoice_num)
            self._after(0, self._cb.on_row, row, (i + 1) / total, i + 1, total, time.time() - self._t0)

            if connection_failed:
                failures.append(invoice_num)
                streak += 1
                if streak >= BRAKE_AFTER:
                    self._after(0, self._cb.on_notice, "Servidor instável, aguardando…")
                    self._wait(BRAKE_SECONDS)
                    streak = 0
            else:
                streak = 0
            if self._pace:
                time.sleep(self._pace)
        return failures

    def _query(self, invoice_num: int) -> tuple[dict, bool]:
        """Row for one invoice and whether it failed by connection. Cancel and session loss propagate."""
        try:
            cte, status, has_image = api.call_with_relogin(
                lambda: self._get_invoice(self._session, invoice_num, stop=self._stop), self._relogin,
            )
            connection_failed = False
        except (api.Cancelled, api.SessionLost):
            raise
        except api.ConnectionFailed:
            cte, status, has_image, connection_failed = "-", CONNECTION_FAILED, "-", True
        except Exception as e:
            cte, status, has_image, connection_failed = "-", api.friendly_error(e), "-", False
        delivery = self._drivers.deliveries.get(invoice_num) if self._drivers else None
        row = {
            "NF-e": invoice_num, "CT-e": cte, "Imagem": has_image, "Status": status,
            "Motorista": delivery.driver if delivery else "",
            "Entrega": delivery.date if delivery else None,
        }
        return row, connection_failed
