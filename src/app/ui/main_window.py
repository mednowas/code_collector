import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import threading
import subprocess
import platform
from datetime import datetime

from app.codebase_collector.collector import collect_codebase
from app.codebase_collector.project_manager import ProjectManager
from app.ui.extension_dialog import ExtensionDialog
from app.utils.paths import get_path

# Настройка темы
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def open_file_explorer(path):
    if not os.path.exists(path): return
    if platform.system() == "Windows": os.startfile(path)
    elif platform.system() == "Darwin": subprocess.Popen(["open", path])
    else: subprocess.Popen(["xdg-open", path])

class AddProjectDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Новый проект")
        self.geometry("400x300")
        self.transient(parent)
        self.grab_set()
        self.attributes("-topmost", True)
        self.result = None
        
        self.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="Название проекта:").pack(anchor="w", padx=20, pady=(20, 5))
        self.name_entry = ctk.CTkEntry(self, placeholder_text="MyCoolProject")
        self.name_entry.pack(fill="x", padx=20)

        ctk.CTkLabel(self, text="Путь к папке:").pack(anchor="w", padx=20, pady=(15, 5))
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=20)
        
        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="C:/Projects/...")
        self.path_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(path_frame, text="...", width=40, command=self._browse).pack(side="right", padx=(5, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=30)
        ctk.CTkButton(btn_frame, text="Создать", command=self._save).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Отмена", command=self.destroy, fg_color="transparent", border_width=1).pack(side="left", padx=10)

    def _browse(self):
        d = filedialog.askdirectory()
        if d:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, d)
            if not self.name_entry.get():
                self.name_entry.insert(0, os.path.basename(d))

    def _save(self):
        name = self.name_entry.get().strip()
        path = self.path_entry.get().strip()
        if name and path:
            self.result = (name, path)
            self.destroy()

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CodeBase Collector v3.0")
        self.geometry("1100x700")
        
        icon_path = get_path(os.path.join("assets", "icon.ico"))
        self.iconbitmap(icon_path)
        # Настройка сетки главного окна:
        # col 0: Sidebar (фиксированный), col 1: Content (растягивается)
        self.grid_columnconfigure(0, weight=0) 
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._setup_sidebar()
        self._setup_content_area()
        
        self.current_project_name = None
        self.refresh_project_list()

    def _setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1) # Список проектов растягивается

        # Заголовок
        ctk.CTkLabel(self.sidebar, text="CODEBASE\nCOLLECTOR", font=("Arial Black", 20)).grid(row=0, column=0, padx=20, pady=20)

        # Кнопки действий
        btn_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        ctk.CTkButton(btn_box, text="+ Проект", command=self.add_project, width=100).pack(side="left", padx=2)
        ctk.CTkButton(btn_box, text="⚙ Global", command=self.open_global_settings, width=80, fg_color="#444444").pack(side="right", padx=2)

        # Список проектов (Scrollable Frame)
        self.project_scroll = ctk.CTkScrollableFrame(self.sidebar, label_text="ВАШИ ПРОЕКТЫ")
        self.project_scroll.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        # Кнопка удаления внизу
        ctk.CTkButton(self.sidebar, text="Удалить выбранный", command=self.delete_project, 
                      fg_color="transparent", text_color="#ff5555", hover_color="#442222").grid(row=3, column=0, pady=10)

    def _setup_content_area(self):
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content.grid_rowconfigure(3, weight=1) # Терминал растягивается
        self.content.grid_columnconfigure(0, weight=1)

        # 1. Header (Имя + Путь экспорта)
        self.header_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        self.lbl_project_name = ctk.CTkLabel(self.header_frame, text="Выберите проект", font=("Segoe UI", 24, "bold"))
        self.lbl_project_name.pack(side="left")
        
        self.btn_open_res = ctk.CTkButton(self.header_frame, text="📂 Открыть папку", command=self.open_result_folder, 
                                          fg_color="#333333", height=32)
        self.btn_open_res.pack(side="right")

        # Лейбл пути (под заголовком)
        self.lbl_export_path = ctk.CTkLabel(self.content, text="Export Path: ---", text_color="#00ccff", font=("Consolas", 12))
        self.lbl_export_path.grid(row=1, column=0, sticky="w", pady=(0, 20))

        # 2. Controls (Фильтры + Кнопка старта)
        self.controls = ctk.CTkFrame(self.content)
        self.controls.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        
        self.btn_filter = ctk.CTkButton(self.controls, text="Настроить фильтры файлов", command=self.open_filter_dialog,
                                        fg_color="#444444", image=None)
        self.btn_filter.pack(side="left", padx=20, pady=20)
        
        self.lbl_filter_info = ctk.CTkLabel(self.controls, text="Расширения не выбраны")
        self.lbl_filter_info.pack(side="left", padx=10)

        self.btn_update = ctk.CTkButton(self.controls, text="🚀 ОБНОВИТЬ БАЗУ ЗНАНИЙ", command=self.run_update,
                                        font=("Segoe UI", 14, "bold"), height=40, state="disabled")
        self.btn_update.pack(side="right", padx=20, pady=20)

        # 3. Terminal
        ctk.CTkLabel(self.content, text="TERMINAL OUTPUT:", font=("Consolas", 12, "bold")).grid(row=3, column=0, sticky="w", pady=(10, 5))
        
        self.log_box = ctk.CTkTextbox(self.content, font=("Consolas", 12), text_color="#00ff00", fg_color="#111111")
        self.log_box.grid(row=4, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    # --- Logic ---

    def log(self, message):
        self.log_box.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def refresh_project_list(self):
        # Очистка списка
        for widget in self.project_scroll.winfo_children():
            widget.destroy()
            
        projects = ProjectManager.load_projects()
        
        for name in projects:
            # Создаем кнопку для каждого проекта (имитация Listbox)
            btn = ctk.CTkButton(self.project_scroll, text=name, anchor="w", fg_color="transparent", 
                                border_width=1, border_color="#333333",
                                command=lambda n=name: self._select_project(n))
            btn.pack(fill="x", pady=2)

    def _select_project(self, name):
        self.current_project_name = name
        self.lbl_project_name.configure(text=name)
        
        config = ProjectManager.get_project_config(name)
        exts = config.get("extensions", [])
        self.lbl_filter_info.configure(text=f"Выбрано типов: {len(exts)}")
        
        self.btn_update.configure(state="normal")
        self._update_export_label()
        
        # Визуальное выделение (можно доработать, меняя цвета кнопок в цикле)
        self.log(f"Выбран проект: {name}")

    def add_project(self):
        dlg = AddProjectDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            name, path = dlg.result
            try:
                ProjectManager.save_project(name, path, extensions=[".py", ".md", ".txt", ".json"])
                self.refresh_project_list()
                self._select_project(name) # Сразу выбираем
                self.log(f"Проект создан: {name}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def delete_project(self):
        if not self.current_project_name: return
        if messagebox.askyesno("Удаление", f"Удалить '{self.current_project_name}' из списка?"):
            ProjectManager.delete_project(self.current_project_name)
            self.current_project_name = None
            self.lbl_project_name.configure(text="Выберите проект")
            self.btn_update.configure(state="disabled")
            self.refresh_project_list()

    def open_global_settings(self):
        curr = ProjectManager.load_global_settings().get("default_export_dir", "")
        new_dir = filedialog.askdirectory(initialdir=curr)
        if new_dir:
            ProjectManager.save_global_settings({"default_export_dir": new_dir})
            self.log(f"Global export dir: {new_dir}")
            self._update_export_label()

    def open_filter_dialog(self):
        if not self.current_project_name: return
        config = ProjectManager.get_project_config(self.current_project_name)
        dlg = ExtensionDialog(self, config.get("extensions", []))
        self.wait_window(dlg)
        if dlg.result is not None:
            ProjectManager.save_project(self.current_project_name, config["path"], 
                                        extensions=dlg.result, ignore_patterns=config.get("ignore_patterns"))
            self.lbl_filter_info.configure(text=f"Выбрано типов: {len(dlg.result)}")
            self.log("Фильтры сохранены.")

    def _get_export_path(self):
        if not self.current_project_name: return None
        gs = ProjectManager.load_global_settings()
        d = gs.get("default_export_dir")
        if d and os.path.exists(d):
            return os.path.join(d, self.current_project_name)
        return None

    def _update_export_label(self):
        p = self._get_export_path()
        if p: self.lbl_export_path.configure(text=f"Save to: {p}", text_color="#00ccff")
        else: self.lbl_export_path.configure(text="Save to: <Будет выбран вручную>", text_color="#ffaa00")

    def open_result_folder(self):
        p = self._get_export_path()
        if p and not os.path.exists(p): p = os.path.dirname(p) # Если папки проекта нет, открыть общую
        if p and os.path.exists(p): open_file_explorer(p)
        else: self.log("Папка экспорта еще не существует.")

    def run_update(self):
        if not self.current_project_name: return
        
        out_dir = self._get_export_path()
        if not out_dir:
            temp = filedialog.askdirectory()
            if not temp: return
            out_dir = os.path.join(temp, self.current_project_name)

        self.btn_update.configure(state="disabled", text="РАБОТАЮ...")
        
        threading.Thread(target=self._worker, args=(self.current_project_name, os.path.dirname(out_dir)), daemon=True).start()

    def _worker(self, name, base_path):
        try:
            self.after(0, lambda: self.log("Начинаю сборку..."))
            res = collect_codebase(name, base_path)
            self.after(0, lambda: self.log(f"ГОТОВО! Файлов: {res['count']}"))
            self.after(0, lambda: self.log(f"Путь: {res['path']}"))
            self.after(0, lambda: messagebox.showinfo("Success", "Сборка завершена!"))
        except Exception as e:
            self.after(0, lambda: self.log(f"ERROR: {e}"))
            print(e)
        finally:
             self.after(0, lambda: self.btn_update.configure(state="normal", text="🚀 ОБНОВИТЬ БАЗУ ЗНАНИЙ"))

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()