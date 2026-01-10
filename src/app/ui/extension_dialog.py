import customtkinter as ctk

class ExtensionDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_extensions):
        super().__init__(parent)
        self.title("Фильтр файлов")
        self.geometry("600x500")
        
        # Делаем окно модальным и поверх всех
        self.transient(parent)
        self.grab_set()
        self.attributes("-topmost", True)
        
        self.result = None
        self.current = set(current_extensions)
        self.vars = {}
        
        # Сетка: строка 0 - панель (фиксирована), строка 1 - контент (растягивается)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_top_bar()
        self._setup_content()

    def _setup_top_bar(self):
        # Панель инструментов сверху
        bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Кнопки управления выбором (слева)
        ctk.CTkButton(bar, text="Выбрать всё", width=100, 
                      command=self._select_all, fg_color="#444444").pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(bar, text="Снять всё", width=100, 
                      command=self._deselect_all, fg_color="#444444").pack(side="left")

        # Кнопки действия (справа)
        ctk.CTkButton(bar, text="Сохранить", width=100, 
                      command=self._save, fg_color="#0e639c").pack(side="right", padx=(5, 0))
        
        ctk.CTkButton(bar, text="Отмена", width=100, 
                      command=self.destroy, fg_color="transparent", border_width=1).pack(side="right")

    def _setup_content(self):
        # Прокручиваемая область
        scroll = ctk.CTkScrollableFrame(self, label_text="Типы файлов")
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Группы
        groups = {
            "Python / Core": [".py", ".pyi", ".ipynb", "__init__.py"],
            "Web Frontend": [".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss"],
            "Config / Data": [".json", ".yaml", ".yml", ".toml", ".env", ".xml", ".csv", ".sql"],
            "Backend / Low Level": [".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".java"],
            "Docs / Text": [".md", ".txt", ".rst", ".log"],
            "DevOps / Shell": [".sh", ".bat", ".ps1", "Dockerfile", "Makefile"]
        }

        row_counter = 0
        for group_name, exts in groups.items():
            # Заголовок группы
            ctk.CTkLabel(scroll, text=group_name, font=("Segoe UI", 12, "bold"), 
                         text_color="#888888").grid(row=row_counter, column=0, sticky="w", pady=(10, 5))
            row_counter += 1
            
            # Чекбоксы (в 3 колонки)
            frame_grid = ctk.CTkFrame(scroll, fg_color="transparent")
            frame_grid.grid(row=row_counter, column=0, sticky="ew")
            row_counter += 1
            
            col = 0
            row = 0
            for ext in exts:
                is_selected = ext in self.current
                var = ctk.BooleanVar(value=is_selected)
                self.vars[ext] = var
                
                chk = ctk.CTkCheckBox(frame_grid, text=ext, variable=var, 
                                      checkbox_width=20, checkbox_height=20, font=("Consolas", 12))
                chk.grid(row=row, column=col, sticky="w", padx=10, pady=5)
                
                col += 1
                if col > 2: # 3 колонки
                    col = 0
                    row += 1

    def _select_all(self):
        for var in self.vars.values(): var.set(True)

    def _deselect_all(self):
        for var in self.vars.values(): var.set(False)

    def _save(self):
        selected = [ext for ext, var in self.vars.items() if var.get()]
        self.result = selected
        self.destroy()