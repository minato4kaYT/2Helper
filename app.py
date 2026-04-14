"""
GTA5RP Helper — Бизнес-помощник для предпринимателей
EMS Трекер + Перекуп Калькулятор + Трекер заработка
"""

import webview
import sqlite3
import json
import os
import csv
import io
import urllib.request
import urllib.error
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS work_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS ems_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            price_per REAL NOT NULL,
            profit_per REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES work_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            comment TEXT,
            category TEXT DEFAULT 'general',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            image_data TEXT,
            purchased_at TEXT NOT NULL,
            purchase_tx_id INTEGER DEFAULT 0,
            sold INTEGER DEFAULT 0,
            sold_price REAL DEFAULT 0,
            sold_at TEXT
        );

        CREATE TABLE IF NOT EXISTS bp_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            bp_value INTEGER NOT NULL DEFAULT 2,
            done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    conn.close()


class Api:
    """API для pywebview — мост между Python и JS."""

    # ─── EMS Трекер ───

    def ems_start_session(self, work_type):
        conn = get_db()
        # Завершаем предыдущую активную сессию
        conn.execute(
            "UPDATE work_sessions SET is_active=0, ended_at=? WHERE is_active=1",
            (datetime.now().isoformat(),)
        )
        cur = conn.execute(
            "INSERT INTO work_sessions (work_type, started_at) VALUES (?, ?)",
            (work_type, datetime.now().isoformat())
        )
        conn.commit()
        sid = cur.lastrowid
        conn.close()
        return sid

    def ems_end_session(self):
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM work_sessions WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        session_id = row["id"] if row else None
        conn.execute(
            "UPDATE work_sessions SET is_active=0, ended_at=? WHERE is_active=1",
            (datetime.now().isoformat(),)
        )
        conn.commit()
        conn.close()
        # Discord notification
        if session_id:
            try:
                self.discord_notify_session_end(session_id)
            except Exception:
                pass
        return True

    def ems_get_active_session(self):
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM work_sessions WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def ems_add_action(self, session_id, action_type):
        # Базовые цены +20% бонус
        prices = {
            "pmp": {"price": 1980, "profit": 1980},        # 1650 * 1.2
            "osmotr": {"price": 226, "profit": 226},       # 188 * 1.2 ≈ 226
            "ukol": {"price": 3600, "profit": 1980},       # 3000*1.2, profit 1650*1.2
        }
        p = prices.get(action_type, {"price": 0, "profit": 0})
        conn = get_db()
        conn.execute(
            "INSERT INTO ems_actions (session_id, action_type, count, price_per, profit_per, created_at) VALUES (?,?,1,?,?,?)",
            (session_id, action_type, p["price"], p["profit"], datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True

    def ems_remove_last_action(self, session_id, action_type):
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM ems_actions WHERE session_id=? AND action_type=? ORDER BY id DESC LIMIT 1",
            (session_id, action_type)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM ems_actions WHERE id=?", (row["id"],))
            conn.commit()
        conn.close()
        return True

    def ems_get_session_stats(self, session_id):
        conn = get_db()
        rows = conn.execute(
            "SELECT action_type, COUNT(*) as cnt, SUM(profit_per) as total_profit, SUM(price_per) as total_price FROM ems_actions WHERE session_id=? GROUP BY action_type",
            (session_id,)
        ).fetchall()
        conn.close()
        stats = {}
        total = 0
        for r in rows:
            stats[r["action_type"]] = {
                "count": r["cnt"],
                "total_profit": r["total_profit"],
                "total_price": r["total_price"]
            }
            total += r["total_profit"]
        return {"actions": stats, "total_profit": total}

    def ems_get_alltime_stats(self):
        """Статистика EMS за ВСЁ время (все смены)."""
        conn = get_db()
        rows = conn.execute(
            "SELECT action_type, COUNT(*) as cnt, SUM(profit_per) as total_profit, SUM(price_per) as total_price FROM ems_actions GROUP BY action_type"
        ).fetchall()
        session_count = conn.execute(
            "SELECT COUNT(*) as c FROM work_sessions"
        ).fetchone()["c"]
        total_time = conn.execute(
            "SELECT SUM(CAST((julianday(ended_at) - julianday(started_at)) * 86400 AS INTEGER)) as secs FROM work_sessions WHERE ended_at IS NOT NULL"
        ).fetchone()["secs"] or 0
        conn.close()
        stats = {}
        total = 0
        for r in rows:
            stats[r["action_type"]] = {
                "count": r["cnt"],
                "total_profit": r["total_profit"],
                "total_price": r["total_price"]
            }
            total += r["total_profit"]
        return {
            "actions": stats,
            "total_profit": total,
            "session_count": session_count,
            "total_time_seconds": total_time
        }

    def ems_get_all_sessions(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT ws.*, COALESCE(SUM(ea.profit_per), 0) as total_profit, COUNT(ea.id) as action_count FROM work_sessions ws LEFT JOIN ems_actions ea ON ea.session_id=ws.id GROUP BY ws.id ORDER BY ws.id DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Транзакции / Перекуп ───

    def tx_add(self, amount, comment, category="general"):
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO transactions (amount, comment, category, created_at) VALUES (?,?,?,?)",
            (amount, comment, category, datetime.now().isoformat())
        )
        conn.commit()
        tid = cur.lastrowid
        conn.close()
        return tid

    def tx_delete(self, tx_id):
        conn = get_db()
        conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        conn.commit()
        conn.close()
        return True

    def tx_get_all(self, category=None):
        conn = get_db()
        if category:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE category=? ORDER BY id DESC",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY id DESC"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def tx_get_totals(self, category=None):
        conn = get_db()
        if category:
            row = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) as income, COALESCE(SUM(CASE WHEN amount<0 THEN amount ELSE 0 END),0) as expense FROM transactions WHERE category=?",
                (category,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) as income, COALESCE(SUM(CASE WHEN amount<0 THEN amount ELSE 0 END),0) as expense FROM transactions"
            ).fetchone()
        conn.close()
        return {"income": row["income"], "expense": row["expense"], "balance": row["income"] + row["expense"]}

    # ─── Инвентарь ───

    def inv_add(self, name, purchase_price, link_to_calc):
        conn = get_db()
        tx_id = 0
        if link_to_calc:
            cur = conn.execute(
                "INSERT INTO transactions (amount, comment, category, created_at) VALUES (?,?,?,?)",
                (-abs(purchase_price), f"Покупка: {name}", "resale", datetime.now().isoformat())
            )
            tx_id = cur.lastrowid
        cur2 = conn.execute(
            "INSERT INTO inventory (name, purchase_price, purchased_at, purchase_tx_id) VALUES (?,?,?,?)",
            (name, purchase_price, datetime.now().isoformat(), tx_id)
        )
        conn.commit()
        iid = cur2.lastrowid
        conn.close()
        return iid

    def inv_sell(self, item_id, sale_price):
        conn = get_db()
        item = conn.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
        if not item:
            conn.close()
            return False
        conn.execute(
            "INSERT INTO transactions (amount, comment, category, created_at) VALUES (?,?,?,?)",
            (sale_price, f"Продажа: {item['name']}", "resale", datetime.now().isoformat())
        )
        conn.execute(
            "UPDATE inventory SET sold=1, sold_price=?, sold_at=? WHERE id=?",
            (sale_price, datetime.now().isoformat(), item_id)
        )
        conn.commit()
        profit = sale_price - item["purchase_price"]
        conn.close()
        # Discord notification
        try:
            self.discord_notify_sale(item["name"], item["purchase_price"], sale_price, profit)
        except Exception:
            pass
        return {"profit": profit, "item_name": item["name"]}

    def inv_delete(self, item_id):
        conn = get_db()
        item = conn.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
        if item and item["purchase_tx_id"]:
            conn.execute("DELETE FROM transactions WHERE id=?", (item["purchase_tx_id"],))
        conn.execute("DELETE FROM inventory WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
        return True

    def inv_get_all(self, show_sold=False):
        conn = get_db()
        if show_sold:
            rows = conn.execute("SELECT * FROM inventory ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM inventory WHERE sold=0 ORDER BY id DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Сохранение файла ───

    def save_file(self, content, default_name):
        """Сохранить файл через диалог."""
        try:
            import webview
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=('JSON files (*.json)',)
            )
            if result:
                path = result if isinstance(result, str) else result[0]
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return path
        except Exception as e:
            # Fallback: save to desktop or current dir
            try:
                path = os.path.join(os.path.expanduser("~"), "Desktop", default_name)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return path
            except Exception:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), default_name)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return path
        return None

    # ─── Статус игры ───

    def check_game_running(self):
        """Проверяет запущена ли GTA5 (Windows)."""
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq GTA5.exe", "/NH"],
                capture_output=True, text=True, timeout=3
            )
            return "GTA5.exe" in result.stdout
        except Exception:
            return False

    # ─── Калькулятор перекупа ───

    def calc_resale(self, buy_price, sell_price, commission_pct, expenses):
        commission = sell_price * (commission_pct / 100)
        net = sell_price - commission
        total_cost = buy_price + expenses
        profit = net - total_cost
        roi = (profit / total_cost * 100) if total_cost > 0 else 0
        breakeven = total_cost / (1 - commission_pct / 100) if commission_pct < 100 else 0
        gov_price = buy_price * 0.5
        return {
            "net_sale": round(net, 2),
            "commission": round(commission, 2),
            "total_cost": round(total_cost, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
            "breakeven": round(breakeven, 2),
            "gov_price": round(gov_price, 2)
        }

    # ─── Экспорт / Очистка ───

    def export_json(self):
        conn = get_db()
        data = {
            "transactions": [dict(r) for r in conn.execute("SELECT * FROM transactions").fetchall()],
            "inventory": [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()],
            "sessions": [dict(r) for r in conn.execute("SELECT * FROM work_sessions").fetchall()],
            "ems_actions": [dict(r) for r in conn.execute("SELECT * FROM ems_actions").fetchall()],
            "exported_at": datetime.now().isoformat()
        }
        conn.close()
        return json.dumps(data, ensure_ascii=False, indent=2)

    # ─── Discord Webhook ───

    def discord_set_webhook(self, url):
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('discord_webhook', ?)",
            (url,)
        )
        conn.commit()
        conn.close()
        return True

    def discord_get_webhook(self):
        conn = get_db()
        row = conn.execute(
            "SELECT value FROM settings WHERE key='discord_webhook'"
        ).fetchone()
        conn.close()
        return row["value"] if row else ""

    def discord_send(self, title, description, color=0x7c5cfc, fields=None):
        conn = get_db()
        row = conn.execute(
            "SELECT value FROM settings WHERE key='discord_webhook'"
        ).fetchone()
        conn.close()
        if not row or not row["value"]:
            return {"ok": False, "error": "Webhook не настроен"}

        webhook_url = row["value"]
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "footer": {"text": "GTA5RP Helper"}
        }
        if fields:
            embed["fields"] = fields

        payload = json.dumps({"embeds": [embed]}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"ok": True, "status": resp.status}
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def discord_test(self):
        return self.discord_send(
            "Тест уведомления",
            "GTA5RP Helper успешно подключён!",
            0x3dd68c
        )

    def discord_notify_session_end(self, session_id):
        stats = self.ems_get_session_stats(session_id)
        a = stats["actions"]
        pmp = a.get("pmp", {"count": 0, "total_profit": 0})
        osm = a.get("osmotr", {"count": 0, "total_profit": 0})
        ukol = a.get("ukol", {"count": 0, "total_profit": 0})

        fields = [
            {"name": "ПМП", "value": f"{pmp['count']} шт. — ${pmp['total_profit']:,.0f}", "inline": True},
            {"name": "Осмотры", "value": f"{osm['count']} шт. — ${osm['total_profit']:,.0f}", "inline": True},
            {"name": "Уколы", "value": f"{ukol['count']} шт. — ${ukol['total_profit']:,.0f}", "inline": True},
        ]
        return self.discord_send(
            "Смена EMS завершена",
            f"**Заработок: ${stats['total_profit']:,.0f}**",
            0x3dd68c,
            fields
        )

    def discord_notify_sale(self, item_name, buy_price, sell_price, profit):
        color = 0x3dd68c if profit >= 0 else 0xf5555d
        fields = [
            {"name": "Покупка", "value": f"${buy_price:,.0f}", "inline": True},
            {"name": "Продажа", "value": f"${sell_price:,.0f}", "inline": True},
            {"name": "Прибыль", "value": f"${profit:,.0f}", "inline": True},
        ]
        return self.discord_send(
            f"Продажа: {item_name}",
            f"**{'Прибыль' if profit >= 0 else 'Убыток'}: ${profit:,.0f}**",
            color,
            fields
        )

    # ─── Бонус Поинты (BP) ───

    def bp_get_tasks(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM bp_tasks ORDER BY id").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def bp_add_task(self, text, bp_value):
        conn = get_db()
        conn.execute(
            "INSERT INTO bp_tasks (text, bp_value, created_at) VALUES (?,?,?)",
            (text, bp_value, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True

    def bp_toggle_task(self, task_id, done):
        conn = get_db()
        conn.execute("UPDATE bp_tasks SET done=? WHERE id=?", (1 if done else 0, task_id))
        conn.commit()
        conn.close()
        return True

    def bp_delete_task(self, task_id):
        conn = get_db()
        conn.execute("DELETE FROM bp_tasks WHERE id=?", (task_id,))
        conn.commit()
        conn.close()
        return True

    def bp_reset_all(self):
        conn = get_db()
        conn.execute("UPDATE bp_tasks SET done=0")
        conn.commit()
        conn.close()
        return True

    def bp_get_total(self):
        conn = get_db()
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN done=1 THEN bp_value ELSE 0 END),0) as earned, COALESCE(SUM(bp_value),0) as total FROM bp_tasks"
        ).fetchone()
        conn.close()
        return {"earned": row["earned"], "total": row["total"]}

    def bp_seed_defaults(self):
        """Заполнить стандартными заданиями если пусто."""
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) as c FROM bp_tasks").fetchone()["c"]
        if count > 0:
            conn.close()
            return False
        tasks = [
            ("3 часа в онлайне", 4),
            ("Нули в казино", 4),
            ("25 действий на стройке", 4),
            ("25 действий в порту", 4),
            ("25 действий в шахте", 4),
            ("3 победы в Дэнс Баттлах", 4),
            ("Два раза оплатить смену внешности у хирурга в EMS", 4),
            ("Добавить 5 видео в кинотеатре", 2),
            ("Выиграть 5 игр в тренировочном комплексе (от 100$)", 2),
            ("Выиграть 3 любых игры на арене (от 100$)", 2),
            ("2 круга на любом маршруте автобусника", 4),
            ("5 раз снять 100% шкуру с животных", 4),
            ("Выиграть гонку в картинге", 2),
            ("10 действий на ферме", 2),
            ("Потушить 25 'огоньков' пожарным", 2),
            ("Выкопать 1 сокровище (не мусор)", 2),
            ("Проехать 1 уличную гонку", 2),
            ("Выполнить 3 заказа дальнобойщиком", 4),
            ("Заказ материалов для бизнеса вручную", 2),
            ("20 подходов в тренажерном зале", 2),
            ("Успешная тренировка в тире", 2),
            ("10 посылок на почте", 2),
            ("Арендовать киностудию", 4),
            ("Купить лотерейный билет", 2),
        ]
        for text, bp in tasks:
            conn.execute(
                "INSERT INTO bp_tasks (text, bp_value, created_at) VALUES (?,?,?)",
                (text, bp, datetime.now().isoformat())
            )
        conn.commit()
        conn.close()
        return True

    # ─── Профили перекупа ───

    def profile_create(self, name):
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('active_profile', ?)",
            (name,)
        )
        conn.commit()
        conn.close()
        return True

    def profile_get_active(self):
        conn = get_db()
        row = conn.execute(
            "SELECT value FROM settings WHERE key='active_profile'"
        ).fetchone()
        conn.close()
        return row["value"] if row else "default"

    # ─── Экспорт / Очистка ───

    def clear_all_data(self):
        conn = get_db()
        conn.executescript("""
            DELETE FROM ems_actions;
            DELETE FROM work_sessions;
            DELETE FROM transactions;
            DELETE FROM inventory;
        """)
        conn.commit()
        conn.close()
        return True


def get_html():
    """Встроенный UI — читает из ui/index.html рядом с exe, или из вшитой строки."""
    # Сначала пробуем файл рядом (для разработки)
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
    if os.path.exists(local):
        return local

    # Для собранного .exe — записываем во временный файл
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "gta5rp_helper_ui.html")
    # Если уже есть — используем
    if os.path.exists(tmp):
        return tmp

    # Иначе — ошибка (UI файл должен быть рядом)
    raise FileNotFoundError(
        "UI файл не найден. Положите папку ui/ рядом с app.py/exe"
    )


def main():
    init_db()
    api = Api()
    ui_path = get_html()
    window = webview.create_window(
        "GTA5RP Helper",
        url=ui_path,
        js_api=api,
        width=1100,
        height=750,
        min_size=(900, 600),
        frameless=True,
        easy_drag=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
