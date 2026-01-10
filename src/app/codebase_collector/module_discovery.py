import os

def discover_modules(project_path):
    """
    Обнаруживает все подмодули в проекте.
    Возвращает список путей к подмодулям.
    Подмодули считаются папками, содержащими '__init__.py' для Python или
    исходные файлы '.c', '.cpp', '.h' для C/C++.
    """
    modules = []
    
    for root, dirs, files in os.walk(project_path):
        # Для Python-модулей
        if "__init__.py" in files:
            modules.append(root)
        # Для C/C++ модулей
        elif any(f.endswith(('.c', '.cpp', '.h')) for f in files):
            modules.append(root)

    return modules
