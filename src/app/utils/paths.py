import os
import sys

def get_path(relative_path: str) -> str:
    """
    Получает абсолютный путь к ресурсу, работающий и в dev, и в exe.
    relative_path должен быть указан относительно папки 'src/app'.
    """
    # Проверка, собрано ли приложение (PyInstaller)
    if getattr(sys, 'frozen', False):
        # Если собрано, базовый путь - это временная папка распаковки
        base_path = sys._MEIPASS
    else:
        # Если разработка.
        # Этот файл лежит в src/app/utils/paths.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Нам нужна папка src/app, поэтому поднимаемся на уровень выше
        base_path = os.path.dirname(current_dir)

    return os.path.join(base_path, relative_path)