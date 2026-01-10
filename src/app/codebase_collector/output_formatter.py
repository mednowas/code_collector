import json
import os

def format_output(result, output_dir):
    """
    Форматирует результат и сохраняет в указанную директорию.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Сохранение в JSON
    with open(os.path.join(output_dir, "result.json"), "w") as file:
        json.dump(result, file, indent=4)

    # Сохранение в текстовый файл
    with open(os.path.join(output_dir, "result.txt"), "w") as file:
        file.write(str(result))
