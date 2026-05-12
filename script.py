import ctypes
import customtkinter as ctk

from config import APP_NAME
from ui.app import App

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

if __name__ == "__main__":
    # Registra o app no Windows para o ícone aparecer corretamente na barra de tarefas
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)
    App().mainloop()
