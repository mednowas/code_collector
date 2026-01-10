import sys
import os

# Добавляем папку src в пути поиска, чтобы Python видел пакет app
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from app.ui.main_window import MainWindow

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()