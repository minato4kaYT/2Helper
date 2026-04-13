"""GTA5RP Helper — Telegram Bot (VPS)"""

import asyncio, time, os, json, sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiocryptopay import AioCryptoPay, Networks

TOKEN = "8738207366:AAHCYDabkP16KGt_I7JgF_eSjEVdp5-H-r8"
CRYPTOPAY_TOKEN = "541458:AA3Hbmp1qPuPugK7K9CdasDnSJEKuhocetn"
FREE_IDS = {678335503, 6059673725}

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)
crypto = AioCryptoPay(token=CRYPTOPAY_TOKEN, network=Networks.MAIN_NET)

# DB
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper.db")
conn = sqlite3.connect(DB, check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.executescript("""
CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT DEFAULT '', first_name TEXT DEFAULT '',
    sub_until INTEGER DEFAULT 0, sub_plan TEXT DEFAULT '', total_paid REAL DEFAULT 0, registered_at INTEGER DEFAULT 0,
    is_connected INTEGER DEFAULT 0, afk_moves INTEGER DEFAULT 0, wheels INTEGER DEFAULT 0, cases INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
    currency TEXT, plan TEXT, inv_id INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', created_at INTEGER);
""")
conn.commit()

PLANS = {"day": {"price":1.0,"days":1,"label":"1 день","emoji":"⚡"},
         "week": {"price":7.0,"days":7,"label":"7 дней","emoji":"🔥"},
         "month": {"price":30.0,"days":30,"label":"30 дней","emoji":"💎"},
         "year": {"price":70.0,"days":365,"label":"1 год","emoji":"👑"}}

def get_user(uid):
    return conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()

def ensure_user(uid, un="", fn=""):
    if not get_user(uid):
        conn.execute("INSERT INTO users (user_id,username,first_name,registered_at) VALUES (?,?,?,?)",
                     (uid,un,fn,int(time.time())))
        conn.commit()
    return get_user(uid)

def has_sub(uid):
    if uid in FREE_IDS: return True
    u = get_user(uid)
    return u and u["sub_until"] > int(time.time())

def add_sub(uid, days, plan, amount):
    u = get_user(uid)
    cur = max(u["sub_until"] or 0, int(time.time()))
    conn.execute("UPDATE users SET sub_until=?,sub_plan=?,total_paid=total_paid+? WHERE user_id=?",
                 (cur+days*86400, plan, amount, uid))
    conn.commit()

def get_sub_info(uid):
    if uid in FREE_IDS: return "FREE ∞"
    u = get_user(uid)
    if not u or u["sub_until"] <= int(time.time()): return None
    left = u["sub_until"] - int(time.time())
    return f"{left//86400}д {(left%86400)//3600}ч"

def update_stats(uid, afk=0, wheels=0, cases=0):
    conn.execute("UPDATE users SET afk_moves=afk_moves+?,wheels=wheels+?,cases=cases+? WHERE user_id=?",
                 (afk,wheels,cases,uid))
    conn.commit()

E = {"star":"5368324170671202286","fire":"5253877736207821121","check":"5255813619702049821",
     "cross":"5298853345241358103","gear":"5879841310902324730","diamond":"5350291836378307462",
     "shield":"5253780051471642059","money":"5893473283696759404","user":"5255835635704408236",
     "back":"5318770787925113164","rocket":"5253590213917158323","crown":"5253877736207821121"}

def pe(k, fb): return f'<tg-emoji emoji-id="{E.get(k,E["star"])}">{fb}</tg-emoji>'

def IKB(text, callback_data=None, url=None, eid=None):
    p = {"text": text}
    if callback_data: p["callback_data"] = callback_data
    if url: p["url"] = url
    if eid and eid in E: p["icon_custom_emoji_id"] = E[eid]
    return InlineKeyboardButton(**p)

# State
_pending_commands = {}
_heartbeats = {}

def push_cmd(uid, cmd):
    try:
        import requests as req
        req.post(f"http://127.0.0.1:7755/command/{uid}", json={"cmd": cmd}, timeout=2)
    except:
        pass

def is_pc_online(uid):
    try:
        import requests as req
        r = req.get(f"http://127.0.0.1:7755/online/{uid}", timeout=2)
        return r.json().get("online", False)
    except:
        return False

# === HANDLERS ===

@router.message(Command("start"))
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "", msg.from_user.first_name or "")
    sub = get_sub_info(uid)
    sub_text = f"{pe('check','✅')} Подписка: <b>{sub}</b>" if sub else f"{pe('cross','❌')} Подписка: <b>не активна</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [IKB("Панель управления", "panel", eid="gear")],
        [IKB("Подписка", "sub_menu", eid="diamond"), IKB("Профиль", "profile", eid="user")],
        [IKB("Как подключить?", "howto", eid="rocket")],
    ])
    await msg.answer(
        f"{pe('star','⭐')} <b>GTA5RP HELPER</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>{pe('shield','🛡')} Anti-AFK — payday и exp\n"
        f"{pe('fire','🎡')} Авто колесо удачи — каждые 4ч\n"
        f"{pe('diamond','📦')} Авто кейсы — каждые 5ч\n"
        f"{pe('gear','📸')} Скриншоты — контроль с телефона</blockquote>\n\n"
        f"{sub_text}\n\n{pe('rocket','🚀')} Управляй ботом из Telegram!", reply_markup=kb)

@router.callback_query(F.data == "back_main")
async def cb_back(cb: CallbackQuery):
    await cmd_start(cb.message)
    await cb.answer()

@router.callback_query(F.data == "panel")
async def cb_panel(cb: CallbackQuery):
    uid = cb.from_user.id
    if not has_sub(uid):
        await cb.answer("❌ Нужна подписка!", show_alert=True); return
    await cb.answer()
    u = get_user(uid)
    pc = "🟢 ПК подключён" if is_pc_online(uid) else "🔴 ПК не подключён"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [IKB("Запустить", "cmd_on", eid="check"), IKB("Остановить", "cmd_off", eid="cross")],
        [IKB("Скриншот", "cmd_screen", eid="gear")],
        [IKB("Anti-AFK вкл", "cmd_afk_on", eid="shield"), IKB("Anti-AFK выкл", "cmd_afk_off", eid="cross")],
        [IKB("Колесо сейчас", "cmd_wheel", eid="fire"), IKB("Кейс сейчас", "cmd_case", eid="diamond")],
        [IKB("Авто-колесо вкл", "cmd_wheels_on", eid="check"), IKB("Авто-колесо выкл", "cmd_wheels_off", eid="cross")],
        [IKB("Авто-кейсы вкл", "cmd_cases_on", eid="check"), IKB("Авто-кейсы выкл", "cmd_cases_off", eid="cross")],
        [IKB("Статистика", "cmd_stats", eid="star")],
        [IKB("Назад", "back_main", eid="back")],
    ])
    await cb.message.edit_text(
        f"{pe('gear','⚙️')} <b>ПАНЕЛЬ УПРАВЛЕНИЯ</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>Статус: <b>{pc}</b>\n"
        f"Anti-AFK: <b>{u['afk_moves'] if u else 0}</b>\n"
        f"Колёс: <b>{u['wheels'] if u else 0}</b>\n"
        f"Кейсов: <b>{u['cases'] if u else 0}</b></blockquote>\n\n"
        f"<i>Выберите действие:</i>", reply_markup=kb)

@router.callback_query(F.data.startswith("cmd_"))
async def cb_cmd(cb: CallbackQuery):
    uid = cb.from_user.id
    if not has_sub(uid):
        await cb.answer("❌ Нужна подписка!", show_alert=True); return
    cmd = cb.data.replace("cmd_", "")
    if cmd == "stats":
        u = get_user(uid)
        online = "🟢 Онлайн" if is_pc_online(uid) else "🔴 Оффлайн"
        sub = get_sub_info(uid)
        await cb.message.edit_text(
            f"{pe('star','📊')} <b>СТАТИСТИКА</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<blockquote>ПК: <b>{online}</b>\nПодписка: <b>{sub or 'нет'}</b>\n"
            f"Anti-AFK: <b>{u['afk_moves'] if u else 0}</b>\n"
            f"Колёс: <b>{u['wheels'] if u else 0}</b>\n"
            f"Кейсов: <b>{u['cases'] if u else 0}</b></blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[IKB("Назад","panel",eid="back")]]))
        await cb.answer(); return
    if not is_pc_online(uid) and uid not in FREE_IDS:
        await cb.answer("🔴 ПК не подключён!\nЗапустите helper.py на ПК", show_alert=True); return
    push_cmd(uid, cmd)
    labels = {"on":"▶ Отправлено на ПК","off":"■ Отправлено на ПК","screen":"📸 Запрос скриншота",
              "afk_on":"🛡 Anti-AFK ВКЛ","afk_off":"🛡 Anti-AFK ВЫКЛ",
              "wheel":"🎡 Кручу колесо...","case":"📦 Открываю кейс...",
              "wheels_on":"🎡 Авто-колесо ВКЛ","wheels_off":"🎡 Авто-колесо ВЫКЛ",
              "cases_on":"📦 Авто-кейсы ВКЛ","cases_off":"📦 Авто-кейсы ВЫКЛ"}
    await cb.answer(labels.get(cmd, "✅ Отправлено"), show_alert=True)

# Subscription
@router.callback_query(F.data == "sub_menu")
async def cb_sub(cb: CallbackQuery):
    await cb.answer()
    sub = get_sub_info(cb.from_user.id)
    status = f"{pe('check','✅')} Активна: <b>{sub}</b>" if sub else f"{pe('cross','❌')} Не активна"
    rows = [[IKB(f"{p['emoji']} {p['label']} — ${p['price']}", f"buy_{k}", eid="diamond")] for k,p in PLANS.items()]
    rows.append([IKB("Назад","back_main",eid="back")])
    await cb.message.edit_text(
        f"{pe('diamond','💎')} <b>ПОДПИСКА</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n{status}\n\n"
        f"<blockquote>⚡ 1 день — <b>$1</b>\n🔥 7 дней — <b>$7</b>\n"
        f"💎 30 дней — <b>$30</b>\n👑 1 год — <b>$70</b> (выгода 83%!)</blockquote>\n\n"
        f"<i>Оплата через CryptoBot (USDT/TON)</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(cb: CallbackQuery):
    plan = PLANS.get(cb.data.replace("buy_",""))
    if not plan: await cb.answer("❌"); return
    try:
        inv = await crypto.create_invoice(amount=plan["price"], asset="USDT",
            description=f"GTA5RP Helper — {plan['label']}", expires_in=1800)
        url = inv.bot_invoice_url or inv.pay_url
        conn.execute("INSERT INTO payments (user_id,amount,currency,plan,inv_id,status,created_at) VALUES (?,?,?,?,?,?,?)",
            (cb.from_user.id,plan["price"],"USDT",cb.data.replace("buy_",""),inv.invoice_id,"pending",int(time.time())))
        conn.commit()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [IKB("Оплатить",url=url,eid="money")],
            [IKB("Проверить оплату",f"chk_{inv.invoice_id}_{cb.data.replace('buy_','')}",eid="check")],
            [IKB("Назад","sub_menu",eid="back")]])
        await cb.message.edit_text(
            f"{pe('money','💰')} <b>ОПЛАТА</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<blockquote>План: <b>{plan['emoji']} {plan['label']}</b>\n"
            f"Сумма: <b>${plan['price']} USDT</b></blockquote>\n\n"
            f"<i>Нажмите «Оплатить», затем «Проверить»</i>", reply_markup=kb)
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)
    await cb.answer()

@router.callback_query(F.data.startswith("chk_"))
async def cb_chk(cb: CallbackQuery):
    parts = cb.data.split("_"); inv_id = int(parts[1]); plan_id = parts[2]
    try:
        invs = await crypto.get_invoices(invoice_ids=[inv_id])
        if not invs or invs[0].status != "paid":
            await cb.answer("⏳ Ещё не оплачено", show_alert=True); return
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True); return
    plan = PLANS[plan_id]
    add_sub(cb.from_user.id, plan["days"], plan_id, plan["price"])
    conn.execute("UPDATE payments SET status='paid' WHERE inv_id=?", (inv_id,)); conn.commit()
    await cb.answer("✅ Оплачено!")
    await cb.message.edit_text(
        f"{pe('check','✅')} <b>ПОДПИСКА АКТИВИРОВАНА!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>План: <b>{plan['emoji']} {plan['label']}</b>\n"
        f"Осталось: <b>{get_sub_info(cb.from_user.id)}</b></blockquote>\n\n"
        f"{pe('rocket','🚀')} Откройте <b>Панель управления</b>!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [IKB("Панель","panel",eid="gear")],[IKB("В меню","back_main",eid="back")]]))
    for aid in FREE_IDS:
        try: await bot.send_message(aid, f"💰 Оплата! {cb.from_user.first_name} — {plan['label']} (${plan['price']})")
        except: pass

@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery):
    await cb.answer()
    u = get_user(cb.from_user.id); sub = get_sub_info(cb.from_user.id)
    reg = time.strftime("%d.%m.%Y", time.localtime(u["registered_at"])) if u and u["registered_at"] else "?"
    await cb.message.edit_text(
        f"{pe('user','👤')} <b>ПРОФИЛЬ</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>ID: <code>{cb.from_user.id}</code>\nИмя: <b>{cb.from_user.first_name}</b>\n"
        f"Регистрация: <b>{reg}</b></blockquote>\n\n"
        f"{pe('diamond','💎')} Подписка: <b>{sub or 'нет'}</b>\n"
        f"{pe('shield','🛡')} Anti-AFK: <b>{u['afk_moves'] if u else 0}</b>\n"
        f"{pe('fire','🎡')} Колёс: <b>{u['wheels'] if u else 0}</b>\n"
        f"{pe('diamond','📦')} Кейсов: <b>{u['cases'] if u else 0}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[IKB("Назад","back_main",eid="back")]]))

@router.callback_query(F.data == "howto")
async def cb_howto(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(
        f"{pe('rocket','🚀')} <b>КАК ПОДКЛЮЧИТЬ</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>1.</b> Оформите подписку\n\n"
        f"<b>2.</b> Скачайте на ПК:\n<code>https://eternaldev.lol/eternalpay/helper.py</code>\n"
        f"<code>https://eternaldev.lol/eternalpay/start.bat</code>\n\n"
        f"<b>3.</b> Запустите <code>start.bat</code>\n\n"
        f"<b>4.</b> В GTA5RP:\n<blockquote>Разрешение: 1440x1080 (5:4)\nРежим: оконный\n"
        f"Запуск от администратора</blockquote>\n\n"
        f"<b>5.</b> F9 или /on в боте\n\n"
        f"<i>Бот собирает payday, крутит колесо и открывает кейсы!</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [IKB("Подписка","sub_menu",eid="diamond")],[IKB("Назад","back_main",eid="back")]]))

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if msg.from_user.id not in FREE_IDS: return
    total = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    active = conn.execute("SELECT COUNT(*) as c FROM users WHERE sub_until>?", (int(time.time()),)).fetchone()["c"]
    rev = conn.execute("SELECT COALESCE(SUM(amount),0) as s FROM payments WHERE status='paid'").fetchone()["s"]
    await msg.answer(f"{pe('crown','👑')} <b>АДМИН</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Юзеров: <b>{total}</b>\nПодписок: <b>{active}</b>\nВыручка: <b>${rev:.2f}</b>")

@router.message(Command("adduser"))
async def cmd_adduser(msg: Message):
    if msg.from_user.id not in FREE_IDS: return
    parts = msg.text.split()
    if len(parts)<2: await msg.answer("/adduser USER_ID"); return
    try:
        FREE_IDS.add(int(parts[1]))
        await msg.answer(f"✅ <code>{parts[1]}</code> → FREE")
    except: await msg.answer("❌")

# API
async def api_heartbeat(request):
    uid = int(request.match_info.get("uid",0))
    _heartbeats[uid] = time.time()
    cmds = _pending_commands.pop(uid, [])
    return web.json_response({"ok":True,"sub":has_sub(uid),"commands":cmds})

async def api_report(request):
    data = await request.json()
    uid = data.get("user_id",0)
    if data.get("type")=="stats":
        update_stats(uid, data.get("afk",0), data.get("wheels",0), data.get("cases",0))
    elif data.get("type")=="notify":
        try: await bot.send_message(uid, f"🎮 {data.get('text','')}")
        except: pass
    return web.json_response({"ok":True})

async def api_check_sub(request):
    uid = int(request.match_info.get("uid",0))
    return web.json_response({"active":has_sub(uid)})



# ============ 5VITO NOTIFICATIONS ============

# Track prices for items
_vito_prices = {}  # item_name -> [{"price": x, "ts": y}, ...]

@router.message(Command("vito"))
async def cmd_vito(msg: Message):
    """Показать отслеживаемые товары 5VITO."""
    uid = msg.from_user.id
    if not _vito_prices:
        await msg.answer(
            f"{pe('diamond','📦')} <b>5VITO ТРЕКЕР</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>Пока нет данных. Уведомления о покупках/продажах\n"
            f"будут появляться автоматически от бота GTA5RP.</i>")
        return
    lines = [f"{pe('diamond','📦')} <b>5VITO ТРЕКЕР</b>\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for item, prices in sorted(_vito_prices.items()):
        if prices:
            last = prices[-1]["price"]
            lines.append(f"  {pe('money','💰')} <b>{item}</b>: {last}$")
    await msg.answer("\n".join(lines))


# Forward 5VITO messages from GTA5RP bot
# This is called from helper.py when it detects a forwarded message
# Catch any message containing 5VITO/DARKVITO (forwarded or typed)
@router.message(F.text.contains("5VITO") | F.text.contains("DARKVITO") | F.text.contains("Вы купили") | F.text.contains("нашелся покупатель"))
async def handle_vito(msg: Message):
    """Parse 5VITO notifications."""
    text = msg.text or ""
    uid = msg.from_user.id
    
    import re
    
    # Buy notification
    buy_match = re.search(r"Вы купили (.+?) \(", text)
    if buy_match:
        item = buy_match.group(1)
        await msg.answer(
            f"{pe('check','📦')} <b>5VITO — Покупка</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<blockquote>{pe('money','🛒')} <b>{item}</b></blockquote>")
        return
    
    # Sell notification
    sell_match = re.search(r"объявлению (.+?) нашелся покупатель.*зачислено ([\d\s]+)", text, re.DOTALL)
    if sell_match:
        item = sell_match.group(1).strip()
        amount = sell_match.group(2).replace(" ", "").strip()
        _vito_prices.setdefault(item, []).append({"price": int(amount), "ts": int(time.time())})
        await msg.answer(
            f"{pe('check','✅')} <b>5VITO — Продажа!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<blockquote>{pe('money','💰')} <b>{item}</b>\n"
            f"Получено: <b>{amount}$</b></blockquote>")
        return
    
    # Generic 5VITO message
    if "5VITO" in text or "DARKVITO" in text:
        short = text[:300]
        await msg.answer(f"{pe('diamond','📦')} <b>5VITO</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n{short}")

# ============ 5VITO TELETHON LISTENER ============
from telethon import TelegramClient as TelethonClient, events as tl_events

tl_client = TelethonClient("/root/mailing/data/mailing", 21536167, "1c8446933e892bb00a9d78fe24c46b38")

async def start_vito_listener():
    """Listen for GTA5RP bot messages via Telethon userbot."""
    try:
        await tl_client.connect()
        if not await tl_client.is_user_authorized():
            print("⚠ Telethon not authorized for 5VITO")
            return

        @tl_client.on(tl_events.NewMessage(incoming=True))
        async def on_gta_msg(event):
            text = event.raw_text or ""
            if "5VITO" not in text and "DARKVITO" not in text:
                return
            
            # Forward to all FREE users
            for uid in FREE_IDS:
                try:
                    import re
                    buy_match = re.search(r"Вы купили (.+?) \(", text)
                    sell_match = re.search(r"объявлению (.+?) нашелся покупатель.*зачислено ([\d\s]+)", text, re.DOTALL)
                    
                    if buy_match:
                        item = buy_match.group(1)
                        await bot.send_message(uid,
                            f"{pe('check','📦')} <b>5VITO — Покупка</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"<blockquote>{pe('money','🛒')} <b>{item}</b></blockquote>")
                    elif sell_match:
                        item = sell_match.group(1).strip()
                        amount = sell_match.group(2).replace(" ", "").strip()
                        await bot.send_message(uid,
                            f"{pe('check','✅')} <b>5VITO — Продажа!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"<blockquote>{pe('money','💰')} <b>{item}</b>\n"
                            f"Получено: <b>{amount}$</b></blockquote>")
                    else:
                        short = text[:300]
                        await bot.send_message(uid,
                            f"{pe('diamond','📦')} <b>5VITO</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n{short}")
                except Exception as e:
                    print(f"5VITO notify error: {e}")

        print("📦 5VITO listener: ON (Telethon)")
    except Exception as e:
        print(f"⚠ 5VITO listener failed: {e}")


async def main():
    # API runs separately via api_server.py + uvicorn
    me = await bot.get_me()
    print(f"🎮 GTA5RP Helper Bot: @{me.username}")
    print(f"👥 Users: {conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']}")
    print(f"🔑 Free: {FREE_IDS}")
    print(f"🌐 API: http://0.0.0.0:7755")
    await start_vito_listener()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
