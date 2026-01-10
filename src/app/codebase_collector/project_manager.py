import json
import os
from appdirs import user_data_dir

class ProjectManager:
    APP_NAME = "CodeBaseCollector"
    AUTHOR = "User"
    
    @staticmethod
    def _get_config_dir():
        config_dir = user_data_dir(ProjectManager.APP_NAME, ProjectManager.AUTHOR)
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @staticmethod
    def _get_projects_file():
        return os.path.join(ProjectManager._get_config_dir(), "projects.json")

    @staticmethod
    def _get_global_settings_file():
        return os.path.join(ProjectManager._get_config_dir(), "settings.json")

    # --- Global Settings ---
    @staticmethod
    def load_global_settings():
        path = ProjectManager._get_global_settings_file()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {"default_export_dir": ""}

    @staticmethod
    def save_global_settings(settings):
        with open(ProjectManager._get_global_settings_file(), "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)

    # --- Project Management ---
    @staticmethod
    def load_projects():
        path = ProjectManager._get_projects_file()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    @staticmethod
    def save_project(name, path, extensions=None, ignore_patterns=None):
        projects = ProjectManager.load_projects()
        
        # Дефолтные значения
        if ignore_patterns is None:
            # Если проект уже был, сохраняем старые игноры, иначе берем дефолт
            ignore_patterns = projects.get(name, {}).get("ignore_patterns", 
                ["venv", ".git", "__pycache__", "node_modules", "dist", ".idea", ".vscode"])
        
        if extensions is None:
             extensions = projects.get(name, {}).get("extensions", [".py", ".md", ".txt"])

        projects[name] = {
            "path": path,
            "extensions": extensions, # Список расширений
            "ignore_patterns": ignore_patterns,
            "last_updated": None
        }
        
        with open(ProjectManager._get_projects_file(), "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=4, ensure_ascii=False)

    @staticmethod
    def get_project_config(name):
        return ProjectManager.load_projects().get(name, {})
    
    @staticmethod
    def delete_project(name):
        projects = ProjectManager.load_projects()
        if name in projects:
            del projects[name]
            with open(ProjectManager._get_projects_file(), "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=4, ensure_ascii=False)