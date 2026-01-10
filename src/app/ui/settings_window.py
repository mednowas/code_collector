# src/ui/settings_window.py

import tkinter as tk
from tkinter import messagebox
from src.codebase_collector import ProjectManager

class SettingsWindow:
    def __init__(self, master, project_path):
        self.master = master
        self.master.title("Настройки проекта")
        self.master.geometry("400x300")
        self.master.config(bg="#2e2e2e")
        
        # Заголовок
        self.label = tk.Label(self.master, text="Настройки проекта", fg="white", bg="#2e2e2e", font=("Helvetica", 16))
        self.label.pack(pady=20)

        # Поле для пути проекта
        self.path_label = tk.Label(self.master, text="Путь к проекту:", fg="white", bg="#2e2e2e", font=("Helvetica", 12))
        self.path_label.pack(pady=5)

        self.path_entry = tk.Entry(self.master, width=50)
        self.path_entry.insert(0, project_path)
        self.path_entry.pack(pady=5)

        # Кнопка для сохранения конфигураций
        self.save_button = tk.Button(self.master, text="Сохранить настройки", command=self.save_config, fg="black", bg="white")
        self.save_button.pack(pady=10)

    def save_config(self):
        """Метод для сохранения конфигурации проекта."""
        project_path = self.path_entry.get()
        
        if not project_path:
            messagebox.showwarning("Предупреждение", "Путь не может быть пустым!")
            return
        
        try:
            config_data = {"project_path": project_path}
            ProjectManager.save_project_config(project_path, config_data)
            messagebox.showinfo("Успех", "Настройки проекта успешно сохранены!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
