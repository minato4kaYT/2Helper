"""
Анти-АФК — защита от кика за бездействие.
Каждые N секунд двигает мышь или нажимает клавишу.
"""

import time
import random

try:
    import pydirectinput
    pydirectinput.PAUSE = 0.05
except ImportError:
    pydirectinput = None
    print("[!] pip install pydirectinput")


def anti_afk_tick():
    """Одно случайное действие чтобы сервер не кикнул."""
    action = random.choice(["mouse", "key"])

    if action == "mouse":
        # Двигаем мышь на случайное маленькое расстояние и обратно
        dx = random.randint(-5, 5)
        dy = random.randint(-5, 5)
        pydirectinput.moveRel(dx, dy)
        time.sleep(0.1)
        pydirectinput.moveRel(-dx, -dy)
    else:
        # Нажимаем случайную безопасную клавишу
        key = random.choice(["shift", "ctrl", "alt"])
        pydirectinput.press(key)


def run(interval=120, duration=None):
    """
    Запуск анти-АФК.

    interval: секунды между действиями (default 2 мин)
    duration: сколько секунд работать (None = бесконечно)
    """
    print(f"[Анти-АФК] Старт. Интервал: {interval}с")
    start = time.time()
    count = 0

    try:
        while True:
            if duration and (time.time() - start) >= duration:
                break

            time.sleep(interval + random.uniform(-10, 10))
            anti_afk_tick()
            count += 1
            print(f"[Анти-АФК] Тик #{count}")

    except KeyboardInterrupt:
        print(f"[Анти-АФК] Стоп. Всего тиков: {count}")


if __name__ == "__main__":
    run()
