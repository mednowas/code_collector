# -*- coding: utf-8 -*-
"""
Сбор кодовой базы в один файл (расширенная версия).
Совместим с прежними опциями и добавляет:
    --exclude-globs "*.min.js,**/snapshots/**"
    --gitignore                 # учитывать правила из .gitignore (требует pathspec)
    --index-json index.json     # сохранить JSON-индекс со списком файлов и причинами пропусков
    --markdown                  # выводить в Markdown c оглавлением и код-блоками
    --preview                   # не записывать результат, только посчитать/показать первые пути
Пример:
    python collect_codebase.py /path/to/project -o codebase.txt --include-ext py,js --exclude-globs "*.min.js"
"""
from __future__ import annotations
import argparse
import os
import sys
import json
from pathlib import Path
from typing import Iterable, Tuple, Set, Dict, Any, Optional
from tokenize import open as py_open

try:
    from pathspec import PathSpec
    _HAS_PATHSPEC = True
except Exception:
    _HAS_PATHSPEC = False

DEFAULT_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".cache",
    "node_modules", "dist", "build", "target", ".next", ".nuxt",
    ".venv", "venv", "env", ".serverless", ".terraform"
}

# Бинарные/нежелательные расширения (не будут включаться никогда)
ALWAYS_SKIP_EXT = {
    ".pyc", ".pyo", ".o", ".a", ".so", ".dll", ".dylib",
    ".class", ".jar", ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".svg",
    ".mp3", ".wav", ".flac", ".mp4", ".mov", ".avi", ".mkv", ".webm", ".lock"
}

# Часто встречающиеся текстовые/кодовые расширения
COMMON_CODE_EXT = {
    ".py", ".ipynb", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".csv", ".tsv",
    ".html", ".htm", ".css", ".scss", ".sass",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala",
    ".c", ".h", ".hpp", ".hh", ".cpp", ".cc", ".m", ".mm",
    ".cs", ".php", ".rb", ".swift", ".sql", ".graphql", ".gql",
    ".dockerfile", "Dockerfile", ".env", ".sh", ".bash", ".bat", ".ps1",
    ".make", "Makefile", ".gradle", "BUILD", "WORKSPACE",
}

HEADER_LINE = "=" * 80

def read_text_smart(path: Path) -> tuple[str, str]:
    """Читает файл в подходящей кодировке. Возвращает (text, encoding)."""
    # 1) Python-файлы: уважать PEP 263
    if path.suffix.lower() == ".py":
        with py_open(str(path)) as fh:
            return fh.read(), "pep263"

    # 2) Попытаться через набор типичных кодировок
    encodings = ("utf-8", "utf-8-sig", "cp1251", "koi8-r", "cp866", "latin-1")
    last_err = None
    for enc in encodings:
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError as e:
            last_err = e
            continue
    # Если уж совсем беда — пробуем без указания (системная локаль)
    try:
        return path.read_text(), "locale"
    except Exception as e:
        # Пробрасываем исходную UnicodeDecodeError, если она была
        raise last_err or e

def is_probably_text(path: Path, max_check_bytes: int = 4096) -> bool:
    """Простая эвристика: файл без NUL-байтов и хорошо декодируется в UTF-8."""
    try:
        with path.open("rb") as f:
            chunk = f.read(max_check_bytes)
        if b"\\x00" in chunk:
            return False
        text = chunk.decode("utf-8", errors="replace")
        replacement_ratio = text.count("�") / max(1, len(text))
        return replacement_ratio < 0.02
    except Exception:
        return False

def should_skip_dir(dirname: str, skip_dirs: Set[str]) -> bool:
    base = os.path.basename(dirname)
    return base in skip_dirs or base.startswith(".git")

def _load_gitignore(root: Path) -> Optional[PathSpec]:
    if not _HAS_PATHSPEC:
        return None
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    try:
        txt = gi.read_text(encoding="utf-8", errors="ignore").splitlines()
        return PathSpec.from_lines("gitwildmatch", txt)
    except Exception:
        return None

def _matches_gitignore(spec: Optional[PathSpec], root: Path, rel: Path) -> bool:
    if not spec:
        return False
    # pathspec ожидает строки POSIX
    return spec.match_file(str(rel.as_posix()))

def is_allowed_file(path: Path, allow_all_text: bool, include_ext: Set[str], max_bytes: int) -> Tuple[bool, str]:
    if not path.is_file():
        return (False, "not a file")
    try:
        size = path.stat().st_size
    except OSError as e:
        return (False, f"stat error: {e}")
    if size > max_bytes:
        return (False, f"too large ({size} > {max_bytes})")
    ext = path.suffix
    name = path.name
    if ext.lower() in ALWAYS_SKIP_EXT:
        return (False, f"binary/ext skipped: {ext}")
    if ext == "" and name in COMMON_CODE_EXT:
        return (True, "allowed by name")
    if allow_all_text:
        if is_probably_text(path):
            return (True, "text heuristic")
        else:
            return (False, "binary heuristic")
    if ext in include_ext or ext.lower() in include_ext:
        return (True, "allowed by ext")
    return (False, f"ext not in include list: {ext or '<none>'}")

def parse_ext_list(s: str | None) -> Set[str]:
    if not s:
        return set()
    out: Set[str] = set()
    for piece in s.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece.startswith("."):
            out.add(piece)
        else:
            out.add("." + piece)
    return out

def parse_csv_list(s: str | None) -> Set[str]:
    if not s:
        return set()
    return {p.strip() for p in s.split(",") if p.strip()}

def collect_files(
    root: Path,
    out_file: Path,
    include_ext: Set[str],
    allow_all_text: bool,
    max_bytes: int,
    extra_skip_dirs: Set[str],
    show_skipped: bool,
    exclude_globs: Set[str] | None = None,
    use_gitignore: bool = False,
    markdown: bool = False,
    index_json: Path | None = None,
    preview: bool = False,
    cancel_flag: Optional["CancelFlag"] = None,
) -> Tuple[int, int, Dict[str, Any]]:
    """Основной сборщик. Возвращает (files_collected, bytes_written, stats_dict)."""
    from fnmatch import fnmatch
    skip_dirs = set(DEFAULT_SKIP_DIRS)
    skip_dirs.update(extra_skip_dirs)
    gitignore_spec = _load_gitignore(root) if use_gitignore else None

    files_collected = 0
    bytes_written = 0
    stats = {
        "root": str(root),
        "written_to": str(out_file),
        "matched": [],        # первые N путей
        "skipped": 0,
        "skipped_examples": [],
        "by_ext": {},         # ext -> count
    }
    matched_preview_limit = 200

    # Заготовки для markdown
    md_parts = []
    toc_lines = []

    if preview:
        out_stream = None
    else:
        out_stream = out_file.open("w", encoding="utf-8", newline="\n")

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            if cancel_flag and cancel_flag.cancelled:
                break
            dirnames[:] = sorted([d for d in dirnames if not should_skip_dir(d, skip_dirs)])
            for fname in sorted(filenames):
                if cancel_flag and cancel_flag.cancelled:
                    break
                fpath = Path(dirpath) / fname
                rel = fpath.relative_to(root)
                rel_posix = rel.as_posix()

                # .gitignore
                if _matches_gitignore(gitignore_spec, root, rel):
                    if show_skipped:
                        print(f"SKIP  {rel}  -> .gitignore")
                    stats["skipped"] += 1
                    if len(stats["skipped_examples"]) < 50:
                        stats["skipped_examples"].append(f"{rel} -> .gitignore")
                    continue

                # exclude_globs
                if exclude_globs and any(fnmatch(rel_posix, pat) for pat in exclude_globs):
                    if show_skipped:
                        print(f"SKIP  {rel}  -> matched exclude_glob")
                    stats["skipped"] += 1
                    if len(stats["skipped_examples"]) < 50:
                        stats["skipped_examples"].append(f"{rel} -> exclude_glob")
                    continue

                allowed, reason = is_allowed_file(
                    fpath, allow_all_text=allow_all_text,
                    include_ext=include_ext, max_bytes=max_bytes
                )
                if not allowed:
                    if show_skipped:
                        print(f"SKIP  {rel}  -> {reason}")
                    stats["skipped"] += 1
                    if len(stats["skipped_examples"]) < 50:
                        stats["skipped_examples"].append(f"{rel} -> {reason}")
                    continue

                # Читаем
                try:
                    content, _used_enc = read_text_smart(fpath)
                except Exception as e:
                    if show_skipped:
                        print(f"SKIP  {rel}  -> read error: {e}")
                    stats["skipped"] += 1
                    if len(stats["skipped_examples"]) < 50:
                        stats["skipped_examples"].append(f"{rel} -> read error")
                    continue

                # учёт расширения
                ext = fpath.suffix.lower() or "(noext)"
                stats["by_ext"][ext] = stats["by_ext"].get(ext, 0) + 1

                if preview:
                    if len(stats["matched"]) < matched_preview_limit:
                        stats["matched"].append(rel_posix)
                    files_collected += 1
                    continue

                if markdown:
                    # Заголовок файла + закладка
                    anchor = rel_posix.replace("/", "-").replace(".", "-")
                    toc_lines.append(f"- [{rel_posix}](#{anchor})")
                    md_parts.append(f"\n\n---\n\n### {rel_posix}\n\n```{ext.strip('.')}\n{content}\n```\n")
                    # bytes count оценим после
                else:
                    header = f"{HEADER_LINE}\nFILE: {rel}\nSIZE: {len(content.encode('utf-8'))} bytes\n{HEADER_LINE}\n"
                    out_stream.write(header)
                    out_stream.write(content)
                    if not content.endswith("\n"):
                        out_stream.write("\n")
                    out_stream.write("\n")
                    files_collected += 1
                    bytes_written += len(header.encode('utf-8')) + len(content.encode('utf-8')) + 1

        if not preview and markdown:
            # Собираем итоговый markdown
            intro = "# Codebase Dump\n\n## Оглавление\n\n" + "\n".join(toc_lines) + "\n"
            body = "".join(md_parts)
            all_md = intro + body
            out_stream.write(all_md)
            bytes_written = len(all_md.encode("utf-8"))
            files_collected = sum(stats["by_ext"].values())

    finally:
        if out_stream:
            out_stream.close()

    # JSON-индекс
    if index_json:
        meta = {
            "root": str(root),
            "output": str(out_file),
            "files_collected": files_collected,
            "bytes_written": bytes_written,
            "by_ext": stats["by_ext"],
            "skipped": stats["skipped"],
            "skipped_examples": stats["skipped_examples"],
            "preview_examples": stats["matched"],
            "markdown": markdown,
        }
        try:
            Path(index_json).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Не удалось записать индекс {index_json}: {e}", file=sys.stderr)

    return files_collected, bytes_written, stats

def dump_tree(root: Path,
              include_ext: Set[str] | None,
              extra_skip_dirs: Set[str],
              exclude_globs: Set[str] | None,
              use_gitignore: bool,
              file: Path) -> None:
    """
    Сохраняет текстовое дерево каталогов/файлов в UTF-8.
    """
    from fnmatch import fnmatch
    skip_dirs = set(DEFAULT_SKIP_DIRS)
    skip_dirs.update(extra_skip_dirs)
    gitignore_spec = _load_gitignore(root) if use_gitignore else None

    lines: list[str] = [f"{root.name}/"]
    prefix_stack: list[str] = []

    def allowed_file(p: Path) -> bool:
        rel_posix = p.relative_to(root).as_posix()
        if _matches_gitignore(gitignore_spec, root, p.relative_to(root)):
            return False
        if exclude_globs and any(fnmatch(rel_posix, pat) for pat in exclude_globs):
            return False
        if include_ext:
            return (p.suffix in include_ext) or (p.suffix.lower() in include_ext)
        return True

    for dirpath, dirnames, filenames in os.walk(root):
        # фильтрация каталогов
        dirnames[:] = sorted([d for d in dirnames if not should_skip_dir(d, skip_dirs)])
        dirnames[:] = [d for d in dirnames 
                       if not _matches_gitignore(gitignore_spec, root, (Path(dirpath)/d).relative_to(root))]
        dirnames[:] = [d for d in dirnames 
                       if not (exclude_globs and any(fnmatch((Path(dirpath)/d).relative_to(root).as_posix(), pat) 
                                                     for pat in exclude_globs))]

        rel = Path(dirpath).relative_to(root)
        depth = 0 if rel == Path(".") else len(rel.parts)
        # гарантировать, что есть строки для текущей директории
        if rel != Path("."):
            # формируем префикс для веток
            prefix = "│   " * (depth - 1) + "├── "
            lines.append(f"{prefix}{rel.name}/")

        # файлы
        for i, fname in enumerate(sorted(filenames)):
            p = Path(dirpath) / fname
            if not allowed_file(p):
                continue
            prefix = "│   " * (len(p.relative_to(root).parents) - 1) + "└── "
            lines.append(f"{prefix}{fname}")

    Path(file).write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(description="Собрать кодовую базу в один текстовый файл.")
    ap.add_argument("root", type=Path, help="Корневая директория проекта")
    ap.add_argument("-o", "--output", type=Path, default=Path("codebase.txt"), help="Файл для записи (по умолчанию codebase.txt)")
    ap.add_argument("--include-ext", type=str, default="", help="Список расширений через запятую (например: py,js,ts,md)")
    ap.add_argument("--all-text", action="store_true", help="Включать любые текстовые файлы (эвристика), игнорируя --include-ext")
    ap.add_argument("--max-bytes", type=int, default=2_000_000, help="Макс. размер одного файла в байтах (по умолчанию 2_000_000)")
    ap.add_argument("--extra-skip-dirs", type=str, default="", help="Доп. директории для пропуска, через запятую")
    ap.add_argument("--show-skipped", action="store_true", help="Показывать, что было пропущено и почему")
    ap.add_argument("--exclude-globs", type=str, default="", help="Исключить пути по glob-маскам, через запятую (пример: \"*.min.js,**/snapshots/**\")")
    ap.add_argument("--gitignore", action="store_true", help="Учитывать .gitignore (требуется пакет pathspec)")
    ap.add_argument("--index-json", type=Path, default=None, help="Сохранить JSON-индекс по результатам сюда")
    ap.add_argument("--markdown", action="store_true", help="Вывод в Markdown с оглавлением и код-блоками")
    ap.add_argument("--preview", action="store_true", help="Предпросмотр без записи (покажет статистику)")

    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Ошибка: корень '{root}' не существует или не является директорией.", file=sys.stderr)
        sys.exit(2)

    include_ext = parse_ext_list(args.include_ext) or COMMON_CODE_EXT
    extra_skip_dirs = {d.strip() for d in args.extra_skip_dirs.split(",") if d.strip()}
    exclude_globs = parse_csv_list(args.exclude_globs)

    files, total_bytes, stats = collect_files(
        root=root,
        out_file=args.output.resolve(),
        include_ext=include_ext,
        allow_all_text=args.all_text,
        max_bytes=args.max_bytes,
        extra_skip_dirs=extra_skip_dirs,
        show_skipped=args.show_skipped,
        exclude_globs=exclude_globs,
        use_gitignore=args.gitignore,
        markdown=args.markdown,
        index_json=args.index_json,
        preview=args.preview,
        cancel_flag=None,
    )

    if args.preview:
        print(f"[PREVIEW] потенциально файлов: {sum(stats['by_ext'].values())}, примеры:")
        for p in stats["matched"][:50]:
            print("  -", p)
    else:
        print(f"Готово: файлов собрано = {files}, записано ≈ {total_bytes} байт в '{args.output}'")

if __name__ == "__main__":
    main()
