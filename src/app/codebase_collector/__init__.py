# Импортируем функции и классы, которые будут использоваться для сбора данных
from .collector import collect_codebase
from .project_manager import ProjectManager
from .module_discovery import discover_modules
from .output_formatter import format_output
from .updater import update_project  # Если эта функция не существует, заменим или удалим
