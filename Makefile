# Makefile для CodeBaseCollector

# Устанавливаем виртуальную среду и зависимости
install:
	poetry install

# Запуск тестов
test:
	poetry run pytest --maxfail=1 --disable-warnings -q

# Автоформатирование с помощью black
format:
	poetry run black src/

# Сборка проекта
build:
	poetry build

# Удаление виртуальной среды
clean:
	poetry env remove python

# Запуск приложения
run:
	poetry run python -m app.ui.main_window
