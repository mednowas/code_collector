# Makefile для автоматизации через Poetry (Windows/macOS/Linux)
APP_NAME := CodebaseCollector
ENTRY := codebase_collector/__main__.py

.PHONY: install run build-exe clean use-py311 export-req rebuild

use-py311:
	poetry env use 3.11

install:
	poetry install

run:
	poetry run python -m codebase_collector

build-exe:
	poetry run pyinstaller --noconsole --onefile --name $(APP_NAME) \
		--add-data "README.md;." \
		$(ENTRY)

# --- Кроссплатформенный clean ---
# На Windows (cmd.exe) нет rm -rf, поэтому используем условие по переменной окружения OS
# и соответствующие команды удаления.
clean:
ifeq ($(OS),Windows_NT)
	@if exist build rmdir /s /q build
	@if exist dist rmdir /s /q dist
	@for %%f in (*.spec) do del /q "%%f" 2>nul
	@echo Cleaned (Windows).
else
	@rm -rf build dist *.spec
	@echo Cleaned (POSIX).
endif

# Полная пересборка
rebuild: clean build-exe

# Экспорт requirements на случай CI без Poetry
export-req:
	poetry export -f requirements.txt --without-hashes -o requirements.txt
	poetry export -f requirements.txt --with dev --without-hashes -o requirements-dev.txt
