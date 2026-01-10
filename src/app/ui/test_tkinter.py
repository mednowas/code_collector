# src/ui/test_tkinter.py

import tkinter as tk

def test_tkinter():
    root = tk.Tk()
    root.title("Тестовое окно Tkinter")
    root.geometry("300x200")
    
    label = tk.Label(root, text="Окно открыто!", font=("Helvetica", 12))
    label.pack(pady=50)
    
    button = tk.Button(root, text="Закрыть", command=root.quit)
    button.pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    test_tkinter()
