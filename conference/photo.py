"""One photo under review: invoice number, delivery date, confirmation and status."""

# Photo has a `date` property, which would shadow the `date` type in the annotations written after it.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Literal

NfeSource = Literal["qr", "ocr", "typed"]
DateSource = Literal["system", "typed"]
# found: PENDENTE, takes an image; approved: APROVADO, takes none; other: any other status, not sent (the
# briefing's "Status desconhecido"); not_found and unavailable: no answer about the receipt.
SystemState = Literal["found", "not_found", "approved", "other", "unavailable"]

MAX_NFE = 999_999_999  # nine digits, as printed on the stub


class Status(Enum):
    """In priority order: the first that applies is the photo's status."""

    DISCARDED = "Descartada"
    UNREAD = "Não lida"
    DUPLICATE = "Duplicata"
    NO_DATE = "Sem data"
    TO_CHECK = "A conferir"
    READY = "Pronta"

    @property
    def label(self) -> str:
        return self.value


class DateLocked(Exception):
    """The portal already has a delivery date: it always wins and is never changed by the app."""


@dataclass(frozen=True)
class SystemInfo:
    """What the portal had for the invoice when it was checked."""

    state: SystemState
    delivery: date | None
    checked_at: datetime
    status: str | None = None  # the receipt status as the portal wrote it, shown for "other"


@dataclass
class Photo:
    name: str  # file name in entrada/, the key of the photo
    file_hash: str
    nfe: int | None = None
    nfe_source: NfeSource | None = None
    rotation: int = 0
    typed_date: date | None = None
    confirmed: bool = False
    system: SystemInfo | None = None
    date_box: tuple[int, int] | None = None
    sharpness: float = 0.0
    discarded: bool = False

    @property
    def date_locked(self) -> bool:
        return self.system is not None and self.system.delivery is not None

    @property
    def date(self) -> date | None:
        return self.system.delivery if self.date_locked else self.typed_date

    @property
    def date_source(self) -> DateSource | None:
        if self.date_locked:
            return "system"
        return "typed" if self.typed_date is not None else None

    def set_nfe(self, nfe: int | None) -> None:
        """A new number is a new invoice: the review and the portal lookup start over."""
        if nfe == self.nfe:
            return
        if nfe is not None and not 1 <= nfe <= MAX_NFE:
            raise ValueError(f"invoice number out of range: {nfe}")
        self.nfe = nfe
        self.nfe_source = "typed" if nfe is not None else None
        self.confirmed = False
        self.system = None

    def set_typed_date(self, value: date | None) -> None:
        if self.date_locked:
            raise DateLocked(self.name)
        if value != self.typed_date:
            self.typed_date = value
            self.confirmed = False


def status_of(photo: Photo, duplicated: bool) -> Status:
    if photo.discarded:
        return Status.DISCARDED
    if photo.nfe is None:
        return Status.UNREAD
    if duplicated:
        return Status.DUPLICATE
    if photo.date is None:
        return Status.NO_DATE
    if not photo.confirmed:
        return Status.TO_CHECK
    return Status.READY
