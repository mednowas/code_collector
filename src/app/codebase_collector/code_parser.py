import ast
import sys

def get_return_values(node: ast.FunctionDef) -> str:
    """
    Ищет все return statement в функции и возвращает их строковое представление.
    """
    returns = []
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value:
            try:
                # ast.unparse восстанавливает код из ноды (Python 3.9+)
                ret_code = ast.unparse(child.value)
                # Если возвращается что-то длинное (dict/list comprehension), обрезаем
                if len(ret_code) > 50:
                    ret_code = ret_code[:47] + "..."
                returns.append(ret_code)
            except:
                returns.append("...")
    
    if not returns:
        return ""
    
    # Убираем дубликаты, сохраняя порядок
    unique = sorted(list(set(returns)), key=lambda x: returns.index(x))
    return " | ".join(unique)

def generate_skeleton_for_file(code: str, filename: str) -> str:
    """
    Создает API-скелет файла с сохранением Type Hints и Return statements.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"# SYNTAX ERROR in {filename}: {e}\n"

    lines = [f"# SKELETON: {filename}"]
    
    # Обрабатываем глобальные переменные (константы), если они аннотированы
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            # CONST: int = 10
            lines.append(ast.unparse(node))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(_process_func(node, indent=0))
        elif isinstance(node, ast.ClassDef):
            lines.append(_process_class(node, indent=0))
            
    return "\n".join(lines) + "\n"

def get_imports(code: str) -> list:
    """
    Извлекает список импортируемых модулей.
    Возвращает список кортежей: (module_name, level)
    level > 0 означает относительный импорт (from . import x)
    """
    try:
        tree = ast.parse(code)
    except:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.level))
            else:
                # from . import x
                imports.append(("", node.level))
    return imports

def _process_func(node, indent=0):
    prefix = "    " * indent
    
    # 1. Декораторы
    decorator_lines = []
    for dec in node.decorator_list:
        decorator_lines.append(f"{prefix}@{ast.unparse(dec)}")
    
    # 2. Сигнатура (def name(args) -> ret:)
    # ast.unparse(node.args) вернет "a: int, b: str = 'x'"
    args_str = ast.unparse(node.args)
    
    # Возвращаемый тип
    ret_annotation = ""
    if node.returns:
        ret_annotation = f" -> {ast.unparse(node.returns)}"
    
    header = f"{prefix}{'async ' if isinstance(node, ast.AsyncFunctionDef) else ''}def {node.name}({args_str}){ret_annotation}:"
    
    # 3. Докстринги и Returns
    body_lines = []
    doc = ast.get_docstring(node)
    if doc:
        # Форматируем докстринг, чтобы он не занимал 100 строк, если он огромный
        doc_lines = doc.split('\n')
        if len(doc_lines) > 1:
            body_lines.append(f'{prefix}    """{doc_lines[0]} ..."""')
        else:
            body_lines.append(f'{prefix}    """{doc}"""')
    
    # Ищем, что возвращает функция
    return_vals = get_return_values(node)
    
    # Формируем тело "заглушки"
    if return_vals:
        body_lines.append(f"{prefix}    ...; return {return_vals}")
    else:
        body_lines.append(f"{prefix}    ...")

    return "\n".join(decorator_lines + [header] + body_lines) + "\n"

def _process_class(node, indent=0):
    prefix = "    " * indent
    
    # Декораторы класса
    decorator_lines = []
    for dec in node.decorator_list:
        decorator_lines.append(f"{prefix}@{ast.unparse(dec)}")

    # Заголовок класса (class A(B):)
    bases = ""
    if node.bases:
        bases = "(" + ", ".join([ast.unparse(b) for b in node.bases]) + ")"
    
    header = f"{prefix}class {node.name}{bases}:"
    
    lines = decorator_lines + [header]
    
    doc = ast.get_docstring(node)
    if doc:
        lines.append(f'{prefix}    """{doc}"""')
    
    # Внутренности класса
    has_content = False
    
    # Сначала поля класса (Type Hints)
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            # x: int = 5
            lines.append(f"{prefix}    {ast.unparse(item)}")
            has_content = True

    # Затем методы
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(_process_func(item, indent + 1))
            has_content = True
        # Вложенные классы
        elif isinstance(item, ast.ClassDef):
            lines.append(_process_class(item, indent + 1))
            has_content = True
    
    if not has_content and not doc:
        lines.append(f"{prefix}    pass")
        
    return "\n".join(lines)