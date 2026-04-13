"""
GTA5RP Helper Bot v2.0
Anti-AFK + Авто колесо + Кейсы + Telegram управление

Запуск: python helper.py
Требования: pip install pydirectinput pyautogui pillow requests
Разрешение: 1440x1080 (5:4), оконный режим
Запускать от Администратора!
"""

import time
import random
import threading
import ctypes
import ctypes.wintypes
import json
import os
import sys
from datetime import datetime, timedelta

# ============ DEPENDENCIES ============

try:
    import pydirectinput
    pydirectinput.PAUSE = 0.03
except ImportError:
    print("[!] pip install pydirectinput")
    sys.exit(1)

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    print("[!] pip install pyautogui")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[!] pip install requests")
    sys.exit(1)

user32 = ctypes.windll.user32
VK_F9 = 0x78

# ============ CONFIG ============

# Telegram
TG_BOT_TOKEN = "8738207366:AAHCYDabkP16KGt_I7JgF_eSjEVdp5-H-r8"
TG_CHAT_ID = 678335503
API_SERVER = "https://eternaldev.lol/helperapi"  # VPS с ботом
HEARTBEAT_INTERVAL = 30  # секунд

# Режим: True = свой ПК (Telegram polling включён), False = ПК клиента (только API)
IS_OWNER = True  # Поменяй на False для клиентских копий

# Таймеры
WHEEL_INTERVAL = 4 * 3600  # 4 часа КД    # 4ч 5мин — колесо удачи
CASE_INTERVAL = 5 * 3600   # 5 часов КД     # 5ч 5мин — бесплатный кейс
AFK_MIN = 120                       # мин интервал анти-афк (сек)
AFK_MAX = 300                       # макс интервал анти-афк (сек)
SCREENSHOT_INTERVAL = 0  # 0 = выключено, только по кнопке/после колеса/кейса          # скриншот в тг каждые 30 мин

# Координаты меню (1440x1080) — ПОДГОНИ ПОД СВОЙ СЕРВЕР!
# F10 меню
COORDS = {
    # Реальные координаты (окно GTA смещено)
    "f10_shop_tab": (1581, 282),     # "Магазин" вкладка сверху
    "f10_roulette_tab": (898, 341),  # "Рулетка" подвкладка

    # Diamond Casino
    "casino_wheel": (789, 639),      # "Колесо удачи" (слева)

    # Колесо удачи
    "wheel_spin": (1272, 900),       # "Крутить колесо"

    # Кейсы — подгоним позже
    "case_dumb": (727, 904),         # "Дурацкий кейс"

    # Навигация
    "back": (600, 300),              # "Назад"
}

# ============ STATE ============

running = False
modules = {
    "afk": True,
    "wheel": True,
    "cases": False,  # ОТКЛЮЧЕНО        # по умолчанию выкл — включается через ТГ
    "screenshots": True,
}

stats = {
    "afk_moves": 0,
    "wheels": 0,
    "cases": 0,
    "paydays": 0,
    "start_time": 0,
    "last_wheel": 0,
    "last_case": 0,
    "last_screenshot": 0,
    "last_afk": 0,
    "errors": 0,
}

CONFIG_FILE = "helper_config.json"


def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({"modules": modules, "coords": COORDS}, f, indent=2)


def load_config():
    global modules, COORDS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                d = json.load(f)
            modules.update(d.get("modules", {}))
            COORDS.update(d.get("coords", {}))
        except:
            pass


# ============ LOGGING ============

log_lines = []

def log(msg, notify=False):
    t = datetime.now().strftime("%H:%M:%S")
    s = "▶" if running else "■"
    line = f"[{t}] [{s}] {msg}"
    print(line)
    log_lines.append(line)
    if len(log_lines) > 200:
        log_lines.pop(0)
    if notify:
        tg_send(msg)


# ============ TELEGRAM ============

def tg_send(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": f"🎮 GTA5RP Helper\n\n{text}"},
            timeout=5,
        )
    except:
        pass


def tg_send_photo(path, caption=""):
    """Отправка скриншота через VPS (обход блокировки api.telegram.org)."""
    try:
        import base64
        with open(path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode()
        resp = requests.post(
            f"{API_SERVER}/send_photo/{TG_CHAT_ID}",
            json={"photo": photo_b64, "caption": caption},
            timeout=20,
        )
        data = resp.json()
        if data.get("ok"):
            log("📸 Скриншот отправлен в Telegram")
        else:
            log(f"📸 Ошибка: {data}")
    except Exception as e:
        log(f"📸 Ошибка отправки: {e}")


# 5VITO: GTA5RP bot ID for detection
GTA5RP_BOT_USERNAMES = ["gta5rp_bot", "gta5rpbot"]

def check_vito_notification(text):
    """Проверить и переслать 5VITO уведомление."""
    if "5VITO" in text or "DARKVITO" in text:
        # Переслать через API на VPS → бот отправит красиво
        try:
            requests.post(
                f"{API_SERVER}/report",
                json={"user_id": TG_CHAT_ID, "type": "notify",
                      "text": f"📦 5VITO\n\n{text[:500]}"},
                timeout=5)
        except:
            pass
        log(f"📦 5VITO уведомление переслано")
        return True
    return False


def tg_poll():
    """Слушать команды + 5VITO уведомления."""
    offset = 0
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 5},
                timeout=10,
            )
            data = resp.json()
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                text = msg.get("text", "").strip()
                uid = msg.get("from", {}).get("id", 0)

                # 5VITO: check forwarded messages from GTA5RP bot
                fwd = msg.get("forward_from", {})
                if fwd.get("is_bot") and fwd.get("username", "").lower() in GTA5RP_BOT_USERNAMES:
                    check_vito_notification(text)
                    continue

                # Check any message with 5VITO/DARKVITO
                if ("5VITO" in text or "DARKVITO" in text) and uid == TG_CHAT_ID:
                    check_vito_notification(text)
                    continue

                if uid != TG_CHAT_ID:
                    continue

                handle_tg_command(text.lower())
        except:
            pass
        time.sleep(3)


def handle_tg_command(cmd):
    global running

    if cmd == "/start" or cmd == "/help":
        tg_send(
            "📋 Команды:\n\n"
            "/status — статус бота\n"
            "/screen — скриншот экрана\n"
            "/on — запустить бот\n"
            "/off — остановить бот\n"
            "/wheel — крутить колесо сейчас\n"
            "/case — открыть кейс сейчас\n"
            "/afk on/off — анти-афк\n"
            "/wheels on/off — авто-колесо\n"
            "/cases on/off — авто-кейсы\n"
            "/stats — статистика\n"
            "/log — последние логи"
        )

    elif cmd == "/status":
        status = "▶ Работает" if running else "■ Остановлен"
        elapsed = ""
        if stats["start_time"]:
            e = int(time.time() - stats["start_time"])
            h, m = divmod(e // 60, 60)
            elapsed = f"\n⏱ Время: {h}ч {m}м"

        next_wheel = ""
        if stats["last_wheel"]:
            nw = int(WHEEL_INTERVAL - (time.time() - stats["last_wheel"]))
            if nw > 0:
                next_wheel = f"\n🎡 Колесо через: {nw // 3600}ч {(nw % 3600) // 60}м"

        tg_send(
            f"Статус: {status}{elapsed}\n\n"
            f"🛡 Anti-AFK: {'✅' if modules['afk'] else '❌'}\n"
            f"🎡 Колесо: {'✅' if modules['wheel'] else '❌'}\n"
            f"📦 Кейсы: {'✅' if modules['cases'] else '❌'}\n"
            f"📸 Скрины: {'✅' if modules['screenshots'] else '❌'}"
            f"{next_wheel}\n\n"
            f"Anti-AFK: {stats['afk_moves']}\n"
            f"Колёс: {stats['wheels']}\n"
            f"Кейсов: {stats['cases']}"
        )

    elif cmd == "/screen":
        take_screenshot(send=True)

    elif cmd == "/on":
        if not running:
            running = True
            t = threading.Thread(target=main_loop, daemon=True)
            t.start()
            tg_send("▶ Бот запущен!")
        else:
            tg_send("Уже работает")

    elif cmd == "/off":
        running = False
        tg_send("■ Бот остановлен")

    elif cmd == "/wheel":
        if running:
            threading.Thread(target=do_wheel, daemon=True).start()
            tg_send("🎡 Кручу колесо...")
        else:
            tg_send("❌ Бот не запущен")

    elif cmd == "/case":
        if running:
            threading.Thread(target=do_case, daemon=True).start()
            tg_send("📦 Открываю кейс...")
        else:
            tg_send("❌ Бот не запущен")

    elif cmd in ("/afk on", "/afk off"):
        modules["afk"] = cmd.endswith("on")
        save_config()
        tg_send(f"🛡 Anti-AFK: {'✅ вкл' if modules['afk'] else '❌ выкл'}")

    elif cmd in ("/wheels on", "/wheels off"):
        modules["wheel"] = cmd.endswith("on")
        save_config()
        tg_send(f"🎡 Авто-колесо: {'✅ вкл' if modules['wheel'] else '❌ выкл'}")

    elif cmd in ("/cases on", "/cases off"):
        modules["cases"] = cmd.endswith("on")
        save_config()
        tg_send(f"📦 Авто-кейсы: {'✅ вкл' if modules['cases'] else '❌ выкл'}")

    elif cmd == "/stats":
        elapsed = int(time.time() - stats["start_time"]) if stats["start_time"] else 0
        h, m = divmod(elapsed // 60, 60)
        tg_send(
            f"📊 Статистика\n\n"
            f"⏱ Время: {h}ч {m}м\n"
            f"🛡 Anti-AFK: {stats['afk_moves']}\n"
            f"🎡 Колёс: {stats['wheels']}\n"
            f"📦 Кейсов: {stats['cases']}\n"
            f"❌ Ошибок: {stats['errors']}"
        )

    elif cmd == "/log":
        last = "\n".join(log_lines[-15:])
        tg_send(f"📋 Логи:\n\n{last}")


# ============ ACTIONS ============

# Скан-коды клавиш
SCAN_CODES = {
    'f10': 0x44, 'f9': 0x43, 'escape': 0x01, 'return': 0x1C,
    'w': 0x11, 's': 0x1F, 'a': 0x1E, 'd': 0x20,
    'e': 0x12, 'b': 0x30, 'space': 0x39,
}

INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.wintypes.WORD), ("wScan", ctypes.wintypes.WORD),
                ("dwFlags", ctypes.wintypes.DWORD), ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_input", _INPUT)]


def _send_scan(scan, up=False):
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki.wScan = scan
    inp.ki.dwFlags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def press(key, delay=0.1):
    """Нажать клавишу — pydirectinput (работает в GTA)."""
    try:
        pydirectinput.press(key)
        time.sleep(delay)
    except Exception as e:
        log(f"Key error [{key}]: {e}")
        stats["errors"] += 1


def click(x, y, delay=0.3):
    """Клик мышкой через pydirectinput (работает в GTA)."""
    try:
        pydirectinput.click(x, y)
        time.sleep(delay)
    except Exception as e:
        log(f"Click error [{x},{y}]: {e}")
        stats["errors"] += 1
        stats["errors"] += 1


def take_screenshot(send=True):
    try:
        # Папка скриншотов
        scr_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        os.makedirs(scr_dir, exist_ok=True)

        # Имя файла с датой
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(scr_dir, f"screen_{ts}.png")

        img = pyautogui.screenshot()
        img.save(path)
        log(f"📸 Скриншот сохранён: {path}")

        # Всегда отправлять в Telegram
        elapsed = int(time.time() - stats["start_time"]) if stats["start_time"] else 0
        h, m = divmod(elapsed // 60, 60)
        tg_send_photo(path,
            f"📸 Скриншот | {datetime.now().strftime('%H:%M:%S')}\n"
            f"⏱ {h}ч {m}м | AFK:{stats['afk_moves']} | 🎡:{stats['wheels']} | 📦:{stats['cases']}")

        stats["last_screenshot"] = time.time()

        # Чистка старых скриншотов (>50 файлов)
        files = sorted(os.listdir(scr_dir))
        if len(files) > 50:
            for f in files[:-50]:
                try: os.remove(os.path.join(scr_dir, f))
                except: pass

        return True
    except Exception as e:
        log(f"Screenshot error: {e}")
        return False


# ============ ANTI-AFK ============

_afk_step = 0

def do_anti_afk():
    """Ходьба по кругу + свист (B) + поворот."""
    global _afk_step
    stats["afk_moves"] += 1

    try:
        # Ходьба по кругу: W → D → S → A
        circle = ['w', 'd', 's', 'a']
        key = circle[_afk_step % 4]
        _afk_step += 1

        pydirectinput.keyDown(key)
        time.sleep(random.uniform(1.0, 2.5))
        pydirectinput.keyUp(key)

        # Доп. действие
        extra = random.choice(["whistle", "look", "none", "none"])
        if extra == "whistle":
            pydirectinput.press('b')  # свист
            time.sleep(0.5)
        elif extra == "look":
            user32.mouse_event(0x0001, random.randint(-200, 200), 0, 0, 0)

    except Exception as e:
        log(f"AFK error: {e}")
        stats["errors"] += 1

    stats["last_afk"] = time.time()
    if stats["afk_moves"] % 10 == 0:
        log(f"Anti-AFK #{stats['afk_moves']}")


# ============ КОЛЕСО УДАЧИ ============

# Цвета кнопок (1440x1080)
# Кнопка "Крутить колесо" когда активна — оранжево-жёлтая
WHEEL_BTN_COLOR_ACTIVE = (230, 180, 50)   # примерный RGB активной кнопки
WHEEL_BTN_CHECK = (720, 860)               # точка проверки цвета на кнопке
# Кнопка "Открыть" кейс когда активна
CASE_BTN_COLOR_ACTIVE = (230, 180, 50)
CASE_BTN_CHECK = (850, 360)

def is_button_active(check_pos, active_color, tolerance=60):
    """Проверить активна ли кнопка по цвету пикселя."""
    try:
        px = pyautogui.pixel(check_pos[0], check_pos[1])
        return all(abs(a - b) <= tolerance for a, b in zip(px, active_color))
    except:
        return True  # если не можем проверить — считаем активной


def focus_gta():
    """Поставить фокус на окно GTA."""
    try:
        # Try all possible window names (including cyrillic variants)
        names = ["RAGE Multiplayer", "RAGЕ Мultiplayеr", "RAGE  Multiplayer",
                 "GTA5", "Grand Theft Auto V", "GTA:V", "FiveM"]
        for name in names:
            hwnd = user32.FindWindowW(None, name)
            if hwnd:
                break
        if not hwnd:
            # Fallback: find any window with RAGE/GTA in title
            hwnd = user32.GetForegroundWindow()
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            return True
    except:
        pass
    return False


def do_wheel():
    log("🎡 Колесо удачи — проверяю...", notify=True)

    try:
        focus_gta()
        # F10 → Магазин → Рулетка → Колесо удачи
        press('f10', 2.0)
        click(*COORDS["f10_shop_tab"], 1.0)     # Магазин
        click(*COORDS["f10_roulette_tab"], 1.0)  # Рулетка
        time.sleep(1.5)
        # Diamond Casino → Колесо удачи (слева)
        click(*COORDS["casino_wheel"], 2.0)

        # Скриншот для проверки КД
        time.sleep(1.0)

        # Скриншот перед попыткой
        take_screenshot()

        # Кнопка активна — крутим!
        click(*COORDS["wheel_spin"], 0.5)
        time.sleep(0.2)
        press('return', 0.3)
        time.sleep(0.2)
        click(*COORDS["wheel_spin"], 0.5)

        stats["wheels"] += 1
        stats["last_wheel"] = time.time()

        # Ждём анимацию
        time.sleep(12)

        # Скриншот результата
        take_screenshot(send=True)

        # Закрыть
        press('escape', 0.5)
        press('escape', 0.5)
        press('escape', 0.5)

        log(f"🎡 Колесо #{stats['wheels']} прокручено!", notify=True)

    except Exception as e:
        log(f"Wheel error: {e}", notify=True)
        stats["errors"] += 1
        press('escape', 0.3)
        press('escape', 0.3)
        press('escape', 0.3)


# ============ КЕЙСЫ ============

def do_case():
    log("📦 Открытие кейса...", notify=True)

    try:
        focus_gta()
        # F10 → Магазин → Рулетка → Кейсы
        press('f10', 2.0)
        click(*COORDS["f10_shop_tab"], 1.0)     # Магазин
        click(*COORDS["f10_roulette_tab"], 1.0)  # Рулетка
        time.sleep(1.5)
        # Diamond Casino → Кейсы (справа)
        click(*COORDS["casino_cases"], 2.0)

        # Скролл вниз до Дурацкого кейса
        for _ in range(5):
            pyautogui.scroll(-3)
            time.sleep(0.3)

        # Нажать на Дурацкий кейс
        time.sleep(0.5)
        click(*COORDS["case_dumb"], 1.5)

        # Скриншот перед попыткой
        take_screenshot()

        # Кнопка "Крутить x1"
        click(*COORDS["case_open"], 0.5)
        time.sleep(0.2)
        press('return', 0.3)
        time.sleep(0.2)
        click(*COORDS["case_open"], 0.5)

        stats["cases"] += 1
        stats["last_case"] = time.time()

        # Ждём анимацию
        time.sleep(12)

        # Скриншот результата
        take_screenshot(send=True)

        # Закрыть
        press('escape', 0.5)
        press('escape', 0.5)
        press('escape', 0.5)

        log(f"📦 Кейс #{stats['cases']} открыт!", notify=True)

    except Exception as e:
        log(f"Case error: {e}", notify=True)
        stats["errors"] += 1
        press('escape', 0.3)
        press('escape', 0.3)
        press('escape', 0.3)


# ============ MAIN LOOP ============

def main_loop():
    global running

    stats["start_time"] = time.time()
    if not stats["last_wheel"]:
        stats["last_wheel"] = time.time() - WHEEL_INTERVAL + 120  # первое через 2 мин
    if not stats["last_case"]:
        stats["last_case"] = time.time()

    log("▶ СТАРТ", notify=True)

    next_afk = time.time() + random.randint(30, 60)  # первый AFK через 30-60с

    while running:
        now = time.time()

        try:
            # Anti-AFK
            if modules["afk"] and now >= next_afk:
                do_anti_afk()
                next_afk = now + random.randint(AFK_MIN, AFK_MAX)

            # Колесо удачи
            if modules["wheel"] and (now - stats["last_wheel"]) >= WHEEL_INTERVAL:
                do_wheel()

            # Кейсы — отключены
            pass

            # Периодический скриншот
            if modules["screenshots"] and SCREENSHOT_INTERVAL > 0 and (now - stats["last_screenshot"]) >= SCREENSHOT_INTERVAL:
                take_screenshot(send=True)

        except Exception as e:
            log(f"Loop error: {e}")
            stats["errors"] += 1

        time.sleep(1)

    elapsed = int(time.time() - stats["start_time"])
    h, m = divmod(elapsed // 60, 60)
    log(f"■ СТОП | {h}ч {m}м | AFK:{stats['afk_moves']} 🎡:{stats['wheels']} 📦:{stats['cases']}", notify=True)


# ============ F9 HOTKEY ============

def server_poll():
    """Поток: heartbeat + получение команд с сервера."""
    global running
    while True:
        try:
            resp = requests.get(f"{API_SERVER}/heartbeat/{TG_CHAT_ID}", timeout=5)
            data = resp.json()

            if not data.get("sub"):
                log("⚠ Подписка неактивна!")

            for cmd_obj in data.get("commands", []):
                cmd = cmd_obj.get("cmd", "")
                log(f"📱 Команда из TГ: {cmd}")

                if cmd == "on" and not running:
                    running = True
                    t = threading.Thread(target=main_loop, daemon=True)
                    t.start()
                elif cmd == "off":
                    running = False
                elif cmd == "screen":
                    take_screenshot(send=True)
                elif cmd == "wheel":
                    threading.Thread(target=do_wheel, daemon=True).start()
                elif cmd == "case":
                    threading.Thread(target=do_case, daemon=True).start()
                elif cmd == "afk_on":
                    modules["afk"] = True
                    log("🛡 Anti-AFK: ВКЛ")
                elif cmd == "afk_off":
                    modules["afk"] = False
                    log("🛡 Anti-AFK: ВЫКЛ")
                elif cmd == "wheels_on":
                    modules["wheel"] = True
                    log("🎡 Авто-колесо: ВКЛ")
                elif cmd == "wheels_off":
                    modules["wheel"] = False
                    log("🎡 Авто-колесо: ВЫКЛ")
                elif cmd == "cases_on":
                    modules["cases"] = True
                    log("📦 Авто-кейсы: ВКЛ")
                elif cmd == "cases_off":
                    modules["cases"] = False
                    log("📦 Авто-кейсы: ВЫКЛ")

        except Exception as e:
            log(f'Heartbeat error: {e}')

        time.sleep(HEARTBEAT_INTERVAL)


def hotkey_loop():
    global running

    prev = False
    while True:
        state = user32.GetAsyncKeyState(VK_F9)
        now = bool(state & 0x8000)

        if now and not prev:
            if running:
                running = False
            else:
                running = True
                t = threading.Thread(target=main_loop, daemon=True)
                t.start()

        prev = now
        time.sleep(0.03)


# ============ MAIN ============

if __name__ == "__main__":
    load_config()

    print("=" * 50)
    print("  GTA5RP Helper Bot v2.0")
    print("  Anti-AFK + Колесо + Кейсы + Telegram")
    print("=" * 50)
    print()
    print(f"  F9 = Старт / Стоп")
    print(f"  Telegram: управление через @twocoredevbot")
    print()
    print(f"  Модули:")
    print(f"    Anti-AFK:  {'ON' if modules['afk'] else 'OFF'}")
    print(f"    Колесо:    {'ON' if modules['wheel'] else 'OFF'}")
    print(f"    Кейсы:     {'ON' if modules['cases'] else 'OFF'}")
    print(f"    Скрины:    {'ON' if modules['screenshots'] else 'OFF'}")
    print()
    print(f"  1440x1080 оконный режим (5:4)")
    print(f"  Запускай от Администратора!")
    print()

    # Telegram polling в отдельном потоке
    # Telegram direct polling (fallback)
    # Telegram polling ОТКЛЮЧЕН - всё через bot.py на VPS
    print("  Telegram: через @twocorehelperbot (VPS)")

    # Server polling (heartbeat + commands)
    srv_thread = threading.Thread(target=server_poll, daemon=True)
    srv_thread.start()

    tg_send(
        "🎮 Helper Bot v2.0 запущен!\n\n"
        f"🛡 Anti-AFK: {'✅' if modules['afk'] else '❌'}\n"
        f"🎡 Колесо: {'✅' if modules['wheel'] else '❌'}\n"
        f"📦 Кейсы: {'✅' if modules['cases'] else '❌'}\n\n"
        "Отправь /help для списка команд"
    )

    print("  Telegram подключён!")
    print("  Ожидание F9 или /on в Telegram...")
    print()

    hotkey_loop()
