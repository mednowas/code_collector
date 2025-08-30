# Codebase Collector (Tkinter)

Графическая утилита для сборки кодовой базы в один файл — с пресетами расширений, предпросмотром, поддержкой `.gitignore`, glob-исключениями и JSON-индексом.

## Возможности

- Выбор директории проекта и файла результата
- Чекбоксы по группам расширений + пресеты
- Предпросмотр без записи: оценка объёма и примеры путей
- Учитывает `.gitignore` (нужен пакет `pathspec`)
- Исключение путей по glob-маскам (`*.min.js,**/snapshots/**`)
- Markdown-вывод и JSON-индекс
- Профили настроек (сохранение/загрузка JSON)
- Логи и «показ пропусков», мягкая отмена
- CLI-совместимость (можно запускать как скрипт без GUI)

## Требования

- Python 3.9+
- Windows / macOS / Linux  
- Для сборки бинарников: **Python < 3.14** (рекомендуется 3.11, PyInstaller не поддерживает 3.14+)

---

## Автоматизация с Poetry + Makefile

Poetry держит зависимости в своём venv, базовое окружение Python остаётся чистым.

### Установка и запуск
```bash
poetry install

# запуск GUI
poetry run codebase-collector
# или
poetry run python -m codebase_collector.app
````

### Привязка к Python 3.11

```bash
poetry env use 3.11
```

### Сборка однофайлового бинарника (.exe на Windows, аналогично на macOS/Linux)

```bash
make build-exe
# либо без make:
poetry run pyinstaller --noconsole --onefile --name CodebaseCollector \
  --paths . \
  --add-data "README.md;." \
  codebase_collector/app.py
```

Файл окажется в `dist/`.

> Хочешь иконку — добавь `--icon icon.ico`.

### Очистка артефактов

```bash
make clean
```


