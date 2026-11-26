import logging
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import local_config
from conference.batch import Batch
from conference.folders import WorkFolder, work_root
from ui import theme
from ui.conference.bottom_bar import BottomBar
from ui.conference.empty_state import EmptyState
from ui.conference.steps import Steps
from ui.icons import get_icon
from ui.widgets.topbar import make_topbar

logger = logging.getLogger(__name__)


class ConferenceView(ctk.CTkFrame):
    """The new upload screen: load the photos of the work folder and review them (Etapa 6)."""

    def __init__(self, parent, user_name: str, on_logout: Callable[[], None], on_back: Callable[[], None] | None,
                 on_legacy: Callable[[], None]):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self._work: WorkFolder | None = None
        self._batch = Batch()
        make_topbar(self, "Upload de canhotos", user_name, on_logout, on_back=on_back)
        main = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        main.pack(fill="both", expand=True, padx=20, pady=(18, theme.SPACE_LG))
        self._build_header(main)
        self.bottom = BottomBar(main, on_legacy=on_legacy)
        self.bottom.pack(side="bottom", fill="x")
        self.empty = EmptyState(main, on_pick=self._pick_folder)
        self.card = ctk.CTkFrame(
            main, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS_CARD,
        )
        self._open(local_config.work_folder())

    def _build_header(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        row.pack(fill="x", pady=(0, 14))
        self.steps = Steps(row)
        self.steps.pack(side="left")
        # Packed only with a work folder: it shows the folder and changes it (D2)
        self.btn_folder = ctk.CTkButton(
            row, text="", image=get_icon("folder", 15, theme.TEXT_MUTED), compound="left", width=0, height=32,
            corner_radius=theme.RADIUS_INPUT, fg_color=theme.SURFACE, hover_color=theme.SURFACE_2, border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT, font=theme.font(theme.FONT_SIZE_BODY, mono=True),
            command=self._pick_folder,
        )

    # ------------------------------------------------------------------
    # PASTA DE TRABALHO
    # ------------------------------------------------------------------

    def _open(self, root: Path | None) -> None:
        if root is None:
            self._show_empty(None)
            return
        if not root.is_dir():
            self._show_empty(f"A pasta {root} não foi encontrada. Selecione a pasta de novo.")
            return
        work = WorkFolder(root)
        try:
            work.ensure()
        except OSError:
            logger.warning("Could not prepare the work folder %s", root, exc_info=True)
            self._show_empty(f"Não foi possível usar a pasta {root}. Selecione outra pasta.")
            return
        self._work = work
        self._show_folder()

    def _pick_folder(self) -> None:
        current = self._work.root if self._work else None
        picked = filedialog.askdirectory(
            parent=self, title="Selecionar a pasta dos canhotos",
            initialdir=str(current) if current and current.is_dir() else None,
        )
        if not picked:
            return
        root = work_root(Path(picked))
        try:
            local_config.set_work_folder(root)
        except OSError:
            # The folder still works for now; it is asked again next time.
            logger.warning("Could not save the work folder %s", root, exc_info=True)
        self._open(root)

    def _show_empty(self, notice: str | None) -> None:
        self._work = None
        self.steps.set_active(1)
        self.btn_folder.pack_forget()
        self.card.pack_forget()
        self.empty.set_notice(notice)
        self.empty.pack(fill="both", expand=True, pady=(0, 14))
        self.bottom.update_summary(self._batch.summary())

    def _show_folder(self) -> None:
        self.steps.set_active(2)
        self.btn_folder.configure(text=f" {self._work.inputs_dir}")
        self.btn_folder.pack(side="right")
        self.empty.pack_forget()
        self.card.pack(fill="both", expand=True, pady=(0, 14))
        self.bottom.update_summary(self._batch.summary())
