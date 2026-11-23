"""Entry point of the "Enviar planilha" uploader. A separate program from script.py: it has its own config file
(enviar_planilha.env, with the Supabase secret key) and its own build (build_enviar.ps1)."""
import ctypes
import logging

import customtkinter as ctk

from sheet_sync.window import SendSheetWindow

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    # Its own taskbar entry and icon, apart from Python and from the Canhotos app
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("enviar-planilha")
    SendSheetWindow().mainloop()
