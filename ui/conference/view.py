import logging
import threading
from collections.abc import Sequence
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import local_config
from conference import progress
from conference.batch import Batch
from conference.folders import INPUT_FOLDER, WorkFolder, snapshot, work_root
from conference.photo import Photo
from ui import theme
from ui.conference.bottom_bar import BottomBar
from ui.conference.empty_state import EmptyState
from ui.conference.photo_list import PhotoList
from ui.conference.steps import Steps
from ui.icons import get_icon
from ui.widgets.banner import Banner
from ui.widgets.buttons import restore_button, show_cancel
from ui.widgets.topbar import make_topbar
from ui.workers.load import LoadWorker
from utils.status import Tone

logger = logging.getLogger(__name__)

_RENDER_INTERVAL_MS = 250
_SAVE_DELAY_MS = 500
_PHOTO_TYPES = [("Fotos", "*.jpg *.jpeg *.png")]
_EMPTY_LIST = "Nenhuma foto na pasta entrada. Use “Adicionar fotos” ou jogue as fotos lá."
_READING = "Lendo as fotos…"
_CANCELLED_LIST = "Leitura cancelada."
_CANCELLED = "Leitura cancelada. As fotos que faltaram são lidas ao abrir o Upload de novo."
_OCR_MISSING = (
    "O OCR não está disponível: as fotos sem QR legível ficaram como “Não lida”. Confira a instalação do Tesseract."
)
_SAVE_FAILED = "Não foi possível salvar o andamento da conferência agora. Ele é salvo de novo na próxima mudança."
_SWITCH_BLOCKED = (
    "Não foi possível salvar o andamento desta pasta, então a pasta não foi trocada. Tente de novo em instantes."
)
_COPY_FAILED ="Não foi possível copiar as fotos para a pasta entrada."


def _prepared(root: Path) -> tuple[WorkFolder | None, str | None]:
    """The work folder with its subfolders created, or None and what to tell the user."""
    if not root.is_dir():
        return None, f"A pasta {root} não foi encontrada. Selecione a pasta de novo."
    work = WorkFolder(root)
    try:
        work.ensure()
    except OSError:
        logger.warning("Could not prepare the work folder %s", root, exc_info=True)
        return None, f"Não foi possível usar a pasta {root}. Selecione outra pasta."
    return work, None


def _ghost_button(parent, icon: str, command: Callable[[], None], mono: bool = False) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text="", image=get_icon(icon, 15, theme.TEXT_MUTED), compound="left", width=0, height=32,
        corner_radius=theme.RADIUS_INPUT, fg_color=theme.SURFACE, hover_color=theme.SURFACE_2, border_width=1,
        border_color=theme.BORDER, text_color=theme.TEXT, text_color_disabled=theme.TEXT_MUTED,
        font=theme.font(theme.FONT_SIZE_BODY, mono=mono), command=command,
    )


class ConferenceView(ctk.CTkFrame):
    """The new upload screen: load the photos of the work folder and review them (Etapa 6)."""

    def __init__(self, parent, user_name: str, on_logout: Callable[[], None], on_back: Callable[[], None] | None,
                 on_legacy: Callable[[], None]):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self._work: WorkFolder | None = None
        self._batch = Batch()
        self._loading = False
        self._replace = True  # the running load reads the whole folder (not only added photos)
        self._stop: threading.Event | None = None
        self._snapshot: dict[str, tuple[int, int]] = {}  # entrada/ as of the last finished load
        self._load_snapshot: dict[str, tuple[int, int]] = {}  # entrada/ as the running load listed it
        self._added: list[Path] = []
        self._render_job: str | None = None
        self._save_job: str | None = None
        self._dirty = False  # photos changed since the last save
        self._add_style: dict = {}
        # Set on Voltar/Sair: worker callbacks already queued must not touch the gone widgets nor save again.
        self._destroyed = False
        self._cancelled = False  # the last load was stopped by Cancelar
        make_topbar(self, "Upload de canhotos", user_name, on_logout, on_back=on_back)
        main = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        main.pack(fill="both", expand=True, padx=20, pady=(18, theme.SPACE_LG))
        self._build_header(main)
        self.banner = Banner(main, theme.BG)
        self.banner.pack(fill="x", pady=(0, theme.SPACE_SM))
        self.bottom = BottomBar(main, on_legacy=on_legacy)
        self.bottom.pack(side="bottom", fill="x")
        self.empty = EmptyState(main, on_pick=self._pick_folder)
        self.card = ctk.CTkFrame(
            main, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS_CARD,
        )
        self.list = PhotoList(self.card)
        self.list.pack(fill="both", expand=True, padx=1, pady=theme.SPACE_SM)
        # Photos dropped in entrada/ through the Explorer show up when the window gets the focus back.
        self._top = self.winfo_toplevel()
        self._focus_binding = self._top.bind("<FocusIn>", self._on_focus, add="+")
        self._open(local_config.work_folder())

    def _build_header(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        row.pack(fill="x", pady=(0, 14))
        self.steps = Steps(row)
        self.steps.pack(side="left")
        # Packed only with a work folder (D2): the folder (clicking changes it) and "Adicionar fotos" (D3)
        self.btn_add = _ghost_button(row, "plus", self._add_photos)
        self.btn_add.configure(text="Adicionar fotos")
        self.btn_folder = _ghost_button(row, "folder", self._pick_folder, mono=True)

    # ------------------------------------------------------------------
    # WORK FOLDER
    # ------------------------------------------------------------------

    def _open(self, root: Path | None) -> None:
        if root is None:
            self._show_empty(None)
            return
        work, problem = _prepared(root)
        if work is None:
            self._show_empty(problem)
            return
        self._show_folder(work)

    def _pick_folder(self) -> None:
        if self._loading:
            return
        current = self._work.root if self._work else None
        picked = filedialog.askdirectory(
            parent=self, title="Selecionar a pasta dos canhotos",
            initialdir=str(current) if current and current.is_dir() else None,
        )
        if not picked:
            return
        root = work_root(Path(picked))
        work, problem = _prepared(root)
        if work is None:
            # A folder that does not work is never saved, and the one already open stays on screen.
            if self._work is None:
                self._show_empty(problem)
            else:
                self.banner.show(Tone.WARNING, problem)
            return
        self._save()  # what was reviewed in the previous folder
        if self._dirty:
            # It could not be saved: switching now would lose it. The user tries again in a moment.
            self.banner.show(Tone.WARNING, _SWITCH_BLOCKED)
            return
        try:
            local_config.set_work_folder(root)
        except OSError:
            # The folder still works for now; it is asked again next time.
            logger.warning("Could not save the work folder %s", root, exc_info=True)
        self._show_folder(work)

    def _show_empty(self, notice: str | None) -> None:
        self._work = None
        self.banner.hide()
        self.steps.set_active(1)
        self.btn_add.pack_forget()
        self.btn_folder.pack_forget()
        self.card.pack_forget()
        self.empty.set_notice(notice)
        self.empty.pack(fill="both", expand=True, pady=(0, 14))
        self.bottom.update_summary(self._batch.summary())

    def _show_folder(self, work: WorkFolder) -> None:
        self._work = work
        self._batch = Batch()
        self._snapshot = {}
        # A failed save of the previous folder must not carry over: saving the still empty batch would wipe
        # this folder's progress.
        self._dirty = False
        if self._save_job is not None:
            self.after_cancel(self._save_job)
            self._save_job = None
        self.banner.hide()
        self.steps.set_active(2)
        self.btn_add.pack(side="right")
        self.btn_folder.pack(side="right", padx=(0, theme.SPACE_SM))
        self.empty.pack_forget()
        self.card.pack(fill="both", expand=True, pady=(0, 14))
        self._read_folder(progress.load(work.inputs_dir))

    def _folder_label(self, detail: str) -> str:
        return f" {self._work.root.name}\\{INPUT_FOLDER}  ·  {detail}"

    # ------------------------------------------------------------------
    # LOADING
    # ------------------------------------------------------------------

    def _read_folder(self, saved: dict[str, Photo]) -> None:
        """Reads entrada/ again: saved photos that did not change are kept, the rest is read (R2, R3)."""
        files = self._work.inputs()
        self._load_snapshot = snapshot(files)
        self._load(files, saved, replace=True)

    def _on_focus(self, _event=None) -> None:
        if self._work is None or self._loading:
            return
        files = self._work.inputs()
        if snapshot(files) != self._snapshot:
            self._read_folder({photo.name: photo for photo in self._batch.visible()})

    def _add_photos(self) -> None:
        if self._loading or self._work is None:
            return
        picked = filedialog.askopenfilenames(parent=self, title="Adicionar fotos", filetypes=_PHOTO_TYPES)
        if not picked:
            return
        try:
            copied = self._work.copy_in(Path(name) for name in picked)
        except OSError:
            # The photos copied before the failure are read when the window gets the focus back.
            logger.warning("Could not copy the photos into %s", self._work.inputs_dir, exc_info=True)
            self.banner.show(Tone.WARNING, _COPY_FAILED)
            return
        if copied:
            self._added = copied
            self._load(copied, {}, replace=False)

    def _load(self, files: Sequence[Path], saved: dict[str, Photo], replace: bool) -> None:
        self._loading = True
        self._replace = replace
        self._stop = threading.Event()
        self.btn_folder.configure(text=self._folder_label("lendo…"), state="disabled")
        self._add_style = show_cancel(self.btn_add, self._cancel)
        worker = LoadWorker(
            files=files, saved=saved, stop_event=self._stop, after_fn=self.after,
            on_known=self._on_known, on_photo=self._on_photo,
            on_done=lambda ocr_unavailable: self._on_loaded(ocr_unavailable, finished=True),
            on_cancel=lambda ocr_unavailable: self._on_loaded(ocr_unavailable, finished=False),
        )
        threading.Thread(target=worker.run, daemon=True).start()
        self._cancelled = False
        if self.banner.visible and self.banner.text == _CANCELLED:
            self.banner.hide()
        # Right away: after a folder switch the list must not keep the previous folder's photos while hashing.
        self._render()

    def _cancel(self) -> None:
        if self._stop is not None:
            self._stop.set()

    def _on_known(self, photos: list[Photo]) -> None:
        if self._destroyed:
            return
        if self._replace:
            self._batch = Batch(photos)  # photos no longer in entrada/ are dropped (R3)
            self._schedule_save()
        self._render()

    def _on_photo(self, photo: Photo, done: int, total: int) -> None:
        if self._destroyed:
            return
        self._batch.add(photo)
        self.btn_folder.configure(text=self._folder_label(f"lendo {done} de {total}"))
        self._schedule_save()
        if self._render_job is None:  # at most every 250 ms while photos arrive
            self._render_job = self.after(_RENDER_INTERVAL_MS, self._render)

    def _on_loaded(self, ocr_unavailable: bool, finished: bool) -> None:
        if self._destroyed:
            return
        self._loading = False
        self.btn_folder.configure(state="normal")
        restore_button(self.btn_add, self._add_style)
        # Also after Cancelar: the folder counts as seen, so a focus does not start again the read the user
        # just stopped. The photos left unread are read when the Upload is opened again or the folder changes.
        if self._replace:
            self._snapshot = self._load_snapshot
        else:
            self._snapshot.update(snapshot(self._added))
        self._cancelled = not finished
        if self._cancelled:
            self.banner.show(Tone.INFO, _CANCELLED)
        if ocr_unavailable:
            self.banner.show(Tone.WARNING, _OCR_MISSING)
        self._render()

    def _render(self) -> None:
        if self._render_job is not None:
            self.after_cancel(self._render_job)
            self._render_job = None
        # On a first open nothing is known yet: the list waits for the first photo instead of calling it empty.
        empty = _READING if self._loading else _CANCELLED_LIST if self._cancelled else _EMPTY_LIST
        self.list.show(self._batch.rows(), empty)
        self.bottom.update_summary(self._batch.summary())
        if not self._loading and self._work is not None:
            count = len(self._batch)
            self.btn_folder.configure(text=self._folder_label(f"{count} foto" if count == 1 else f"{count} fotos"))

    # ------------------------------------------------------------------
    # PROGRESS FILE
    # ------------------------------------------------------------------

    def _schedule_save(self) -> None:
        """Several changes in a row are written once, 500 ms after the last one."""
        if self._destroyed:
            return
        self._dirty = True
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_job = self.after(_SAVE_DELAY_MS, self._save)

    def _save(self) -> None:
        # Always on the UI thread: the temporary file has a fixed name, two saves at once would clash (#43).
        if self._save_job is not None:
            self.after_cancel(self._save_job)
            self._save_job = None
        if self._work is None or not self._dirty:
            return
        try:
            progress.save(self._work.inputs_dir, self._batch.visible())
        except OSError:
            # Held by a sync client or an antivirus (#44): kept dirty, so the next change tries again.
            logger.warning("Could not save the review progress in %s", self._work.inputs_dir, exc_info=True)
            self.banner.show(Tone.WARNING, _SAVE_FAILED)
            return
        self._dirty = False
        if self.banner.visible and self.banner.text == _SAVE_FAILED:
            self.banner.hide()  # saved now: the warning would no longer be true

    def destroy(self) -> None:
        """Voltar, Sair or the old flow: the load stops and what was reviewed is saved."""
        self._cancel()
        if self._render_job is not None:
            self.after_cancel(self._render_job)
            self._render_job = None
        self._top.unbind("<FocusIn>", self._focus_binding)
        self._save()
        self._destroyed = True
        super().destroy()
