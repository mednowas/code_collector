# src/ui/file_selector.py

import tkinter as tk
from tkinter import filedialog

class FileSelector:
    @staticmethod
    def select_directory():
        return filedialog.askdirectory(title="Выберите директорию")
    
    @staticmethod
    def select_file():
        return filedialog.askopenfilename(title="Выберите файл")
