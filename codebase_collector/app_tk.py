# GUI-обёртка для collect_codebase.py
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys
import io
import contextlib
import json
import webbrowser
import platform
import subprocess

try:
    from codebase_collector import collect_codebase as core
except Exception as e:
    raise SystemExit(f"Не удалось импортировать collect_codebase.py: {e}")

EXT_GROUPS = {
    "Python": [".py", ".ipynb"],
    "JS/TS": [".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"],
    "Frontend": [".html", ".htm", ".css", ".scss", ".sass"],
    "Docs": [".md", ".rst", ".txt"],
    "Data": [".csv", ".tsv", ".json"],
    "Config": [".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".env"],
    "Shell/Batch": [".sh", ".bash", ".bat", ".ps1"],
    "C/C++": [".c", ".h", ".hpp", ".hh", ".cpp", ".cc"],
    "JVM": [".java", ".kt", ".kts", ".scala"],
    "Other": [".go", ".rs", ".cs", ".php", ".rb", ".swift", ".sql", ".graphql", ".gql"],
}
ALL_KNOWN_EXTS = sorted({ext for exts in EXT_GROUPS.values() for ext in exts})

class CancelFlag:
    def __init__(self):
        self.cancelled = False
    def cancel(self):
        self.cancelled = True

class ExtDialog(tk.Toplevel):
    def __init__(self, master, current_exts: set[str]):
        super().__init__(master)
        self.title("Выбор расширений")
        self.transient(master)
        self.grab_set()

        self.vars = {}
        self.result = None

        top = ttk.Frame(self); top.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(top, text="Выбрать всё", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(top, text="Снять всё", command=self._select_none).pack(side=tk.LEFT, padx=6)

        presets = {
            "Только Python": set(EXT_GROUPS["Python"]),
            "Frontend": set(EXT_GROUPS["JS/TS"] + EXT_GROUPS["Frontend"] + EXT_GROUPS["Docs"]),
            "Весь код": set(ALL_KNOWN_EXTS),
            "Минимум (py, md)": {".py", ".md"},
        }
        self._preset_var = tk.StringVar(value="")
        preset_box = ttk.Frame(top); preset_box.pack(side=tk.RIGHT)
        ttk.Label(preset_box, text="Пресет:").pack(side=tk.LEFT, padx=(0,6))
        cb = ttk.Combobox(preset_box, textvariable=self._preset_var, values=list(presets.keys()), width=18, state="readonly")
        cb.pack(side=tk.LEFT)
        def apply_preset(*_):
            name = self._preset_var.get()
            if name in presets:
                self._apply_selection(presets[name])
        cb.bind("<<ComboboxSelected>>", apply_preset)

        container = ttk.Frame(self); container.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        canvas = tk.Canvas(container, highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for group, exts in EXT_GROUPS.items():
            lf = ttk.LabelFrame(inner, text=group)
            lf.pack(fill=tk.X, padx=4, pady=4)
            row = ttk.Frame(lf); row.pack(fill=tk.X, padx=6, pady=4)
            for i, ext in enumerate(exts):
                var = tk.BooleanVar(value=(ext in current_exts))
                self.vars[ext] = var
                ttk.Checkbutton(row, text=ext, variable=var).grid(row=i//6, column=i%6, sticky="w", padx=6, pady=2)

        btns = ttk.Frame(self); btns.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(btns, text="OK", command=self._ok).pack(side=tk.RIGHT, padx=6)

        self.minsize(560, 420)
        self.wait_visibility()
        self.focus()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _collect_selection(self) -> set[str]:
        return {ext for ext, v in self.vars.items() if v.get()}

    def _apply_selection(self, selected: set[str]):
        for ext, var in self.vars.items():
            var.set(ext in selected)

    def _select_all(self):
        self._apply_selection(set(self.vars.keys()))

    def _select_none(self):
        self._apply_selection(set())

    def _ok(self):
        self.result = self._collect_selection()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Codebase Collector")
        self.geometry("860x600")

        self.src_dir = tk.StringVar(value=str(Path.cwd()))
        self.out_file = tk.StringVar(value=str(Path.cwd() / "codebase.txt"))
        self.include_ext = tk.StringVar(value="py,js,ts,md")
        self.all_text = tk.BooleanVar(value=False)
        self.show_skipped = tk.BooleanVar(value=False)
        self.max_bytes = tk.IntVar(value=2_000_000)
        self.extra_skip_dirs = tk.StringVar(value="")
        self.exclude_globs = tk.StringVar(value="")
        self.use_gitignore = tk.BooleanVar(value=True)
        self.markdown = tk.BooleanVar(value=False)
        self.index_json = tk.BooleanVar(value=True)

        self.cancel_flag = CancelFlag()
        self.running = False
        self.worker = None

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True)

        row = ttk.Frame(frm); row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="Директория проекта:").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.src_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(row, text="Выбрать…", command=self.choose_src).pack(side=tk.LEFT)

        row = ttk.Frame(frm); row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="Файл результата:").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.out_file).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(row, text="Выбрать…", command=self.choose_out).pack(side=tk.LEFT)
        ttk.Button(row, text="Открыть папку", command=self.open_result_dir).pack(side=tk.LEFT, padx=6)

        grid = ttk.LabelFrame(frm, text="Опции")
        grid.pack(fill=tk.X, **pad)

        r1 = ttk.Frame(grid); r1.pack(fill=tk.X, **pad)
        ttk.Label(r1, text="Расширения для включения (через запятую):").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.include_ext).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="Расширения…", command=self.open_ext_dialog).pack(side=tk.LEFT)

        r2 = ttk.Frame(grid); r2.pack(fill=tk.X, **pad)
        ttk.Label(r2, text="Доп. директории для пропуска (через запятую):").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.extra_skip_dirs).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        r3 = ttk.Frame(grid); r3.pack(fill=tk.X, **pad)
        ttk.Label(r3, text="Исключить (glob-маски, через запятую):").pack(side=tk.LEFT)
        ttk.Entry(r3, textvariable=self.exclude_globs).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        r4 = ttk.Frame(grid); r4.pack(fill=tk.X, **pad)
        ttk.Label(r4, text="Макс. размер файла, байт:").pack(side=tk.LEFT)
        ttk.Entry(r4, textvariable=self.max_bytes, width=12).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(r4, text="Включать любые текстовые файлы (эвристика)", variable=self.all_text).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(r4, text="Учитывать .gitignore", variable=self.use_gitignore).pack(side=tk.LEFT, padx=6)

        r5 = ttk.Frame(grid); r5.pack(fill=tk.X, **pad)
        ttk.Checkbutton(r5, text="Показывать пропуски", variable=self.show_skipped).pack(side=tk.LEFT)
        ttk.Checkbutton(r5, text="Вывод в Markdown", variable=self.markdown).pack(side=tk.LEFT, padx=12)
        ttk.Checkbutton(r5, text="Сохранять JSON-индекс рядом", variable=self.index_json).pack(side=tk.LEFT, padx=12)

        btns = ttk.Frame(frm); btns.pack(fill=tk.X, **pad)
        self.preview_btn = ttk.Button(btns, text="Предпросмотр", command=self.preview, width=18)
        self.preview_btn.pack(side=tk.LEFT)
        self.start_btn = ttk.Button(btns, text="Собрать", command=self.start, width=18)
        self.start_btn.pack(side=tk.LEFT, padx=6)
        self.stop_btn = ttk.Button(btns, text="Остановить", command=self.stop, state=tk.NORMAL if self.running else tk.DISABLED, width=18)
        self.stop_btn.pack(side=tk.LEFT, padx=6)
        self.open_btn = ttk.Button(btns, text="Открыть результат", command=self.open_result, width=18)
        self.open_btn.pack(side=tk.LEFT, padx=6)
        self.profile_save_btn = ttk.Button(btns, text="Сохранить профиль…", command=self.save_profile)
        self.profile_save_btn.pack(side=tk.RIGHT)
        self.profile_load_btn = ttk.Button(btns, text="Загрузить профиль…", command=self.load_profile)
        self.profile_load_btn.pack(side=tk.RIGHT, padx=6)

        logbox = ttk.LabelFrame(frm, text="Лог")
        logbox.pack(fill=tk.BOTH, expand=True, **pad)
        self.log = tk.Text(logbox, height=18)
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.insert(tk.END, "Готов.\n")

        status = ttk.Frame(self); status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="")
        ttk.Label(status, textvariable=self.status_var, anchor="w").pack(fill=tk.X, padx=8, pady=4)

    def choose_src(self):
        d = filedialog.askdirectory(initialdir=self.src_dir.get())
        if d:
            self.src_dir.set(d)

    def choose_out(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt",
                                         filetypes=[("Text", "*.txt"), ("Markdown", "*.md"), ("All files", "*.*")],
                                         initialfile=Path(self.out_file.get()).name,
                                         initialdir=str(Path(self.out_file.get()).parent))
        if f:
            self.out_file.set(f)

    def open_result_dir(self):
        p = Path(self.out_file.get()).parent
        if not p.exists():
            messagebox.showinfo("Папка результата", f"Каталог ещё не существует: {p}")
            return
        if platform.system() == "Windows":
            os.startfile(str(p))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(p)])
        else:
            subprocess.run(["xdg-open", str(p)])

    def open_result(self):
        p = Path(self.out_file.get())
        if p.exists():
            webbrowser.open(p.as_uri())
        else:
            messagebox.showinfo("Файл результата", f"Файл пока не найден: {p}")

    def _parse_include_ext_var(self) -> set[str]:
        raw = self.include_ext.get().strip()
        if not raw:
            return set(ALL_KNOWN_EXTS)
        out = set()
        for piece in raw.split(","):
            piece = piece.strip()
            if not piece:
                continue
            if not piece.startswith("."):
                piece = "." + piece
            out.add(piece.lower())
        return {e for e in out if e in ALL_KNOWN_EXTS} or set(ALL_KNOWN_EXTS)

    def open_ext_dialog(self):
        current = self._parse_include_ext_var()
        dlg = ExtDialog(self, current)
        self.wait_window(dlg)
        if dlg.result is not None:
            value = ",".join(sorted(ext[1:] for ext in dlg.result))
            self.include_ext.set(value)

    def preview(self):
        if self.running: return
        ok = self._validate_paths()
        if not ok: return
        self._run_job(preview=True)

    def start(self):
        if self.running: return
        ok = self._validate_paths(create_output_parent=True)
        if not ok: return
        self._run_job(preview=False)

    def stop(self):
        if not self.running: return
        self.cancel_flag.cancel()
        self.status_var.set("Запрошена остановка…")

    def _validate_paths(self, create_output_parent: bool=False) -> bool:
        root = Path(self.src_dir.get())
        if not root.exists() or not root.is_dir():
            messagebox.showerror("Ошибка", f"Директория не найдена: {root}")
            return False
        out = Path(self.out_file.get())
        if create_output_parent and not out.parent.exists():
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать каталог для вывода: {e}")
                return False
        return True

    def _run_job(self, preview: bool):
        root = Path(self.src_dir.get())
        out = Path(self.out_file.get())
        include_ext = core.parse_ext_list(self.include_ext.get()) or core.COMMON_CODE_EXT
        extra_skip_dirs = {d.strip() for d in self.extra_skip_dirs.get().split(",") if d.strip()}
        exclude_globs = {g.strip() for g in self.exclude_globs.get().split(",") if g.strip()}
        allow_all_text = self.all_text.get()
        show_skipped = self.show_skipped.get()
        max_bytes = int(self.max_bytes.get())
        use_gitignore = self.use_gitignore.get()
        markdown = self.markdown.get()
        index_json_path = (out.with_suffix(out.suffix + ".index.json")) if self.index_json.get() else None

        self.running = True
        self.cancel_flag = CancelFlag()
        self.start_btn.config(state=tk.DISABLED)
        self.preview_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.insert(tk.END, "Старт...\n")
        self.status_var.set("Работаем…")

        def work():
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    files, total_bytes, stats = core.collect_files(
                        root=root,
                        out_file=out.resolve(),
                        include_ext=include_ext,
                        allow_all_text=allow_all_text,
                        max_bytes=max_bytes,
                        extra_skip_dirs=extra_skip_dirs,
                        show_skipped=show_skipped,
                        exclude_globs=exclude_globs,
                        use_gitignore=use_gitignore,
                        markdown=markdown,
                        index_json=index_json_path,
                        preview=preview,
                        cancel_flag=self.cancel_flag,
                    )
                    if preview:
                        result = f"[PREVIEW] потенциально файлов: {sum(stats['by_ext'].values())}\n"
                        for p in stats["matched"][:50]:
                            print("  -", p)
                    else:
                        result = f"Готово: файлов собрано = {files}, записано ≈ {total_bytes} байт в '{out}'\n"
                except Exception as e:
                    result = f"Ошибка: {e}\n"

            log_text = buf.getvalue() + result
            self.after(0, self._finish, log_text)

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _finish(self, log_text):
        self.log.insert(tk.END, log_text)
        self.log.see(tk.END)
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.preview_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Готово." if "Ошибка" not in log_text else "Ошибка. Смотри лог.")
        if "Готово:" in log_text:
            messagebox.showinfo("Готово", "Операция завершена.")

    def save_profile(self):
        f = filedialog.asksaveasfilename(defaultextension=".json",
                                         filetypes=[("JSON", "*.json"), ("All files", "*.*")],
                                         initialfile="collector_profile.json")
        if not f: return
        data = {
            "src_dir": self.src_dir.get(),
            "out_file": self.out_file.get(),
            "include_ext": self.include_ext.get(),
            "all_text": self.all_text.get(),
            "show_skipped": self.show_skipped.get(),
            "max_bytes": int(self.max_bytes.get()),
            "extra_skip_dirs": self.extra_skip_dirs.get(),
            "exclude_globs": self.exclude_globs.get(),
            "use_gitignore": self.use_gitignore.get(),
            "markdown": self.markdown.get(),
            "index_json": self.index_json.get(),
        }
        Path(f).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Профиль", "Профиль сохранён.")

    def load_profile(self):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not f: return
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать профиль: {e}")
            return
        self.src_dir.set(data.get("src_dir", self.src_dir.get()))
        self.out_file.set(data.get("out_file", self.out_file.get()))
        self.include_ext.set(data.get("include_ext", self.include_ext.get()))
        self.all_text.set(bool(data.get("all_text", self.all_text.get())))
        self.show_skipped.set(bool(data.get("show_skipped", self.show_skipped.get())))
        self.max_bytes.set(int(data.get("max_bytes", self.max_bytes.get())))
        self.extra_skip_dirs.set(data.get("extra_skip_dirs", self.extra_skip_dirs.get()))
        self.exclude_globs.set(data.get("exclude_globs", self.exclude_globs.get()))
        self.use_gitignore.set(bool(data.get("use_gitignore", self.use_gitignore.get())))
        self.markdown.set(bool(data.get("markdown", self.markdown.get())))
        self.index_json.set(bool(data.get("index_json", self.index_json.get())))
        messagebox.showinfo("Профиль", "Профиль загружен.")

if __name__ == "__main__":
    App().mainloop()


def run_app():
    App().mainloop()

if __name__ == '__main__':
    run_app()
