import os
import json
import pathspec
from datetime import datetime
from collections import defaultdict
from .code_parser import generate_skeleton_for_file, get_imports
from .project_manager import ProjectManager

MAX_FILE_SIZE = 2_000_000

def load_gitignore(root_path):
    gitignore_path = os.path.join(root_path, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)
    return None

def count_tokens(text):
    """
    Пытается использовать tiktoken (точность GPT-4), иначе эвристика.
    """
    try:
        import tiktoken
        # cl100k_base - кодировщик для GPT-4 и GPT-3.5
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception: 
        return len(text) // 4

def get_module_name_from_path(root_project, folder_path):
    rel = os.path.relpath(folder_path, root_project)
    if rel == ".": return "root"
    parts = rel.split(os.sep)
    if parts[0] in ["src", "lib", "app"] and len(parts) > 1:
        parts = parts[1:]
    return "-".join(parts)

def is_module_root(dir_path, files_in_dir):
    has_init = "__init__.py" in files_in_dir
    has_readme = any(f.lower().startswith("readme") for f in files_in_dir)
    return has_init and has_readme

def resolve_import_path(base_file_rel_path, import_name, import_level, all_files_set):
    """
    Пытается найти, на какой реальный файл указывает импорт.
    """
    if import_level > 0:
        # Относительный импорт (from .utils import x)
        # base_file: src/model/pipeline.py -> dir: src/model
        current_dir = os.path.dirname(base_file_rel_path)
        # Поднимаемся вверх на level-1
        for _ in range(import_level - 1):
            current_dir = os.path.dirname(current_dir)
        
        # Вариант 1: импорт файла (from . import utils -> src/model/utils.py)
        candidate = os.path.join(current_dir, f"{import_name}.py").replace("\\", "/")
        if candidate in all_files_set: return candidate
        
        # Вариант 2: импорт папки (from . import coords -> src/model/coords/__init__.py)
        candidate_pkg = os.path.join(current_dir, import_name, "__init__.py").replace("\\", "/")
        if candidate_pkg in all_files_set: return candidate_pkg
        
    else:
        # Абсолютный импорт (from src.model import utils)
        # Превращаем точки в слеши
        path_part = import_name.replace(".", "/")
        
        candidate = f"{path_part}.py"
        if candidate in all_files_set: return candidate
        
        candidate_pkg = f"{path_part}/__init__.py"
        if candidate_pkg in all_files_set: return candidate_pkg
        
        # Пробуем добавить src/ если не нашли (частая структура)
        candidate_src = f"src/{path_part}.py"
        if candidate_src in all_files_set: return candidate_src
        
    return None

def collect_codebase(project_name, base_export_dir):
    config = ProjectManager.get_project_config(project_name)
    root_path = config.get("path")
    target_exts = set(ext.lower() for ext in config.get("extensions", []))
    ignore_patterns = config.get("ignore_patterns", [])
    
    gitignore = load_gitignore(root_path)
    module_roots = []
    
    # --- 1. Discovery & Indexing ---
    all_files_rel_paths = set() # Для резолвинга импортов
    
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ignore_patterns]
        rel_root = os.path.relpath(root, root_path).replace("\\", "/")
        
        if root == root_path:
            module_roots.append(root)
        elif is_module_root(root, files):
            module_roots.append(root)
            
        for f in files:
            # Сохраняем относительные пути (src/main.py) для поиска
            rel_path = f if rel_root == "." else f"{rel_root}/{f}"
            all_files_rel_paths.add(rel_path)

    # --- 2. Collection ---
    modules_data = defaultdict(lambda: {"code": [], "skel": [], "readmes": [], "children": set(), "token_count": 0})
    dependency_edges = set()
    files_count = 0
    
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ignore_patterns]
        
        # Deepest Parent Logic
        owner_path = None
        best_len = -1
        for mod_root in module_roots:
            if root.startswith(mod_root):
                if len(mod_root) > best_len:
                    best_len = len(mod_root)
                    owner_path = mod_root
        
        if not owner_path: owner_path = root_path
        if root in module_roots and root != owner_path:
            child_name = get_module_name_from_path(root_path, root)
            modules_data[owner_path]["children"].add(child_name)

        rel_dir = os.path.relpath(root, root_path)

        for file in files:
            file_abs = os.path.join(root, file)
            rel_file = os.path.join(rel_dir, file).replace("\\", "/")
            
            if gitignore and gitignore.match_file(rel_file): continue
            if os.path.getsize(file_abs) > MAX_FILE_SIZE: continue

            ext = os.path.splitext(file)[1].lower()
            
            try:
                with open(file_abs, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                tokens = count_tokens(content)

                if file.lower().startswith("readme"):
                    modules_data[owner_path]["readmes"].append((rel_file, content))
                
                if ext in target_exts:
                    header = f"\n{'='*40}\nFILE: {rel_file}\nTOKENS: {tokens}\n{'='*40}\n"
                    modules_data[owner_path]["code"].append(header + content)
                    modules_data[owner_path]["token_count"] += tokens
                    files_count += 1
                    
                    if ext == ".py":
                        skel = generate_skeleton_for_file(content, rel_file)
                        if skel:
                            modules_data[owner_path]["skel"].append(skel)
                        
                        # --- Graph Building ---
                        # Находим все импорты в файле
                        imports = get_imports(content)
                        for imp_name, level in imports:
                            # Пытаемся понять, ссылается ли импорт на файл внутри нашего проекта
                            target_file = resolve_import_path(rel_file, imp_name, level, all_files_rel_paths)
                            if target_file:
                                # Добавляем ребро в граф (Файл -> Файл)
                                dependency_edges.add(f'    "{rel_file}" --> "{target_file}"')

            except Exception as e:
                print(f"Error {rel_file}: {e}")

    # --- 3. Export ---
    final_output_dir = os.path.join(base_export_dir, project_name)
    dir_code = os.path.join(final_output_dir, "code")
    dir_skel = os.path.join(final_output_dir, "signatures")
    dir_docs = os.path.join(final_output_dir, "readmes")
    
    for d in [dir_code, dir_skel, dir_docs]:
        os.makedirs(d, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # Save Modules
    for mod_path, data in modules_data.items():
        mod_name = get_module_name_from_path(root_path, mod_path)
        total_tokens = data["token_count"]
        
        lines = [
            f"# MODULE: {mod_name}", 
            f"# DATE: {timestamp}", 
            f"# TOTAL TOKENS: {total_tokens} (approx. {total_tokens/1000:.1f}k)",
            ""
        ]
        
        if data["children"]:
            lines.append("# >>> INCLUDED SUBMODULES:")
            for child in sorted(data["children"]):
                lines.append(f"#     - {child}")
            lines.append("# " + "-"*30)

        for path, txt in data["readmes"]:
             lines.append(f"\n# DOCUMENTATION ({path}):\n{txt}\n")

        lines.extend(data["code"])
        
        if lines:
            with open(os.path.join(dir_code, f"{mod_name}.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        if data["skel"]:
            with open(os.path.join(dir_skel, f"{mod_name}_API.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(data["skel"]))

    # All Readmes
    all_readmes = []
    for mod_path, data in modules_data.items():
        for path, txt in data["readmes"]:
            all_readmes.append(f"\n{'='*40}\nFILE: {path}\n{'='*40}\n{txt}")
    if all_readmes:
        with open(os.path.join(dir_docs, "ALL_READMES.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(all_readmes))

    # Architecture JSON
    tree = {"project": project_name, "modules": sorted([get_module_name_from_path(root_path, p) for p in modules_data.keys()])}
    with open(os.path.join(final_output_dir, "architecture.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

    # --- Mermaid Export ---
    # Создаем граф только если есть связи
    if dependency_edges:
        mermaid_lines = ["graph TD"]
        # Стили узлов (опционально)
        mermaid_lines.append("    node [shape=box, style=filled, fillcolor=\"#f9f9f9\", fontname=\"Consolas\"]")
        mermaid_lines.extend(sorted(list(dependency_edges)))
        
        with open(os.path.join(final_output_dir, "dependencies.mermaid"), "w", encoding="utf-8") as f:
            f.write("\n".join(mermaid_lines))

    return {"count": files_count, "path": final_output_dir}