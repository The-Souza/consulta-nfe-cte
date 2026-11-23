"""Decides when a saved sheet should be sent, from its modification time checked every few seconds."""
from typing import Literal

Action = Literal["idle", "confirm", "send"]


class ChangeWatcher:
    """A new modification time first asks for a confirmation check; it is sent only when the next check
    sees the same time, so a sheet Excel is still writing isn't read halfway. Each save is sent once."""

    def __init__(self, sent_mtime: float | None):
        self._sent = sent_mtime
        self._pending: float | None = None

    def tick(self, mtime: float | None) -> Action:
        """`mtime` None means the file is missing for now (Excel replaces it while saving)."""
        if mtime is None:
            return "idle"
        if self._pending is None:
            if mtime == self._sent:
                return "idle"
            self._pending = mtime
            return "confirm"
        if mtime != self._pending:
            self._pending = mtime
            return "confirm"
        self._sent, self._pending = mtime, None
        return "send"

    def retry(self) -> None:
        """The last send failed: the same save is sent again by the next checks."""
        self._sent = None
