"""The photos of one review: filters, batch dates, confirmation, navigation and duplicates.

It only changes the photos in memory: moving files (discarding) is up to the caller.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal

from conference.photo import Photo, Status, status_of


class Chip(Enum):
    ALL = "Todas"
    ATTENTION = "Atenção"
    NO_DATE = "Sem data"
    TO_CHECK = "A conferir"
    READY = "Prontas"

    @property
    def label(self) -> str:
        return self.value


_CHIP_STATUSES = {
    Chip.ATTENTION: {Status.UNREAD, Status.DUPLICATE},
    Chip.NO_DATE: {Status.NO_DATE},
    Chip.TO_CHECK: {Status.TO_CHECK},
    Chip.READY: {Status.READY},
}


class MissingField(Exception):
    """A photo cannot be confirmed without an invoice number and a date."""

    def __init__(self, field: Literal["nfe", "date"]):
        super().__init__(field)
        self.field = field


class DuplicateUnresolved(Exception):
    """A duplicate is resolved first ("Comparar as duas"), so it is clear which photo belongs to the invoice."""


@dataclass(frozen=True)
class Summary:
    ready: int
    ready_dates: list[date]
    pending: int


class Batch:
    def __init__(self, photos: Iterable[Photo] = ()):
        self._photos: dict[str, Photo] = {}
        for photo in photos:
            self.add(photo)

    def __len__(self) -> int:
        return len(self._photos)

    def add(self, photo: Photo) -> None:
        """Adds a photo, or replaces the one with the same name, keeping the name order."""
        self._photos[photo.name] = photo
        self._photos = dict(sorted(self._photos.items(), key=lambda item: item[0].casefold()))

    def photo(self, name: str) -> Photo:
        return self._photos[name]

    def visible(self) -> list[Photo]:
        """The photos still in the review, in name order."""
        return [photo for photo in self._photos.values() if not photo.discarded]

    def duplicates(self) -> dict[int, list[str]]:
        by_nfe: dict[int, list[str]] = {}
        for photo in self.visible():
            if photo.nfe is not None:
                by_nfe.setdefault(photo.nfe, []).append(photo.name)
        return {nfe: names for nfe, names in by_nfe.items() if len(names) > 1}

    def _duplicated_names(self) -> set[str]:
        return {name for names in self.duplicates().values() for name in names}

    def status(self, name: str) -> Status:
        return status_of(self._photos[name], name in self._duplicated_names())

    def _statuses(self) -> dict[str, Status]:
        duplicated = self._duplicated_names()
        return {photo.name: status_of(photo, photo.name in duplicated) for photo in self.visible()}

    def rows(self) -> list[tuple[Photo, Status]]:
        """The visible photos with their status, in name order: the duplicates are worked out once."""
        statuses = self._statuses()
        return [(photo, statuses[photo.name]) for photo in self.visible()]

    def filtered(self, chip: Chip) -> list[Photo]:
        if chip is Chip.ALL:
            return self.visible()
        statuses = self._statuses()
        return [photo for photo in self.visible() if statuses[photo.name] in _CHIP_STATUSES[chip]]

    def counts(self) -> dict[Chip, int]:
        statuses = list(self._statuses().values())
        counts = {chip: sum(status in wanted for status in statuses) for chip, wanted in _CHIP_STATUSES.items()}
        return {Chip.ALL: len(statuses), **counts}

    def batch_dates(self) -> list[date]:
        """The dates already used in the review, oldest first: the 1–9 shortcuts use the first nine."""
        return sorted({photo.date for photo in self.visible() if photo.date is not None})

    def apply_date(self, names: Iterable[str], value: date) -> int:
        """Types `value` on the given photos, skipping those with a system date. Returns how many changed."""
        changed = 0
        for name in names:
            photo = self._photos[name]
            if photo.discarded or photo.date_locked or photo.typed_date == value:
                continue
            photo.set_typed_date(value)
            changed += 1
        return changed

    def confirm(self, name: str) -> None:
        photo = self._photos[name]
        if photo.nfe is None:
            raise MissingField("nfe")
        if name in self._duplicated_names():
            raise DuplicateUnresolved(name)
        if photo.date is None:
            raise MissingField("date")
        photo.confirmed = True

    def confirm_many(self, names: Iterable[str]) -> int:
        """Confirms the photos that have an invoice number and a date and are not duplicates: which photo of
        a duplicate stays is decided when comparing them. Returns how many changed (ready ones do not count)."""
        statuses = self._statuses()
        confirmed = 0
        for name in names:
            if statuses.get(name) is Status.TO_CHECK:
                self._photos[name].confirmed = True
                confirmed += 1
        return confirmed

    def next_pending(self, after: str | None) -> str | None:
        """The next photo that is not ready, after `after` and wrapping around; `after` itself comes last.

        `after` may already be discarded (the user discarded the current photo): its place in the name order
        still counts, so the review goes on from there and not from the top.
        """
        statuses = self._statuses()
        names = list(self._photos)
        start = names.index(after) + 1 if after in self._photos else 0
        for name in names[start:] + names[:start]:
            if name in statuses and statuses[name] is not Status.READY:
                return name
        return None

    def discard(self, name: str) -> None:
        self._photos[name].discarded = True

    def keep(self, name: str, other: str) -> None:
        """Keeps `name` and discards `other`, its duplicate.

        Both share the invoice number, so the portal lookup of the discarded one moves over when the kept one
        has none yet, and so does its typed date when the kept one still has no date. The kept photo goes
        back to "to check": a confirmation given while it was a duplicate did not decide which photo belongs
        to the invoice.
        """
        kept, dropped = self._photos[name], self._photos[other]
        dropped.discarded = True
        if kept.system is None and dropped.system is not None:
            kept.system = dropped.system
        if kept.date is None and dropped.typed_date is not None:
            kept.set_typed_date(dropped.typed_date)
        kept.confirmed = False

    def wrong_number(self, name: str) -> None:
        self._photos[name].set_nfe(None)

    def summary(self) -> Summary:
        statuses = self._statuses()
        ready = [self._photos[name] for name, status in statuses.items() if status is Status.READY]
        return Summary(
            ready=len(ready),
            ready_dates=sorted({photo.date for photo in ready}),
            pending=len(statuses) - len(ready),
        )
