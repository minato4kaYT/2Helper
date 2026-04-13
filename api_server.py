"""Standalone API server for GTA5RP Helper (port 7755)"""
import time, sqlite3, os, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FREE_IDS = {678335503, 6059673725}
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper.db")
conn = sqlite3.connect(DB, check_same_thread=False)
conn.row_factory = sqlite3.Row

_heartbeats = {}
_pending_commands = {}

def has_sub(uid):
    if uid in FREE_IDS: return True
    row = conn.execute("SELECT sub_until FROM users WHERE user_id=?", (uid,)).fetchone()
    return row and row["sub_until"] > int(time.time())

@app.get("/heartbeat/{uid}")
def heartbeat(uid: int):
    _heartbeats[uid] = time.time()
    cmds = _pending_commands.pop(uid, [])
    return {"ok": True, "sub": has_sub(uid), "commands": cmds}

@app.get("/sub/{uid}")
def check_sub(uid: int):
    return {"active": has_sub(uid)}

@app.post("/report")
async def report(data: dict = {}):
    return {"ok": True}

@app.post("/command/{uid}")
async def push_command(uid: int, data: dict = {}):
    cmd = data.get("cmd", "")
    if cmd:
        _pending_commands.setdefault(uid, []).append({"cmd": cmd, "ts": int(time.time())})
    return {"ok": True}

@app.get("/online/{uid}")
def is_online(uid: int):
    last = _heartbeats.get(uid, 0)
    return {"online": (time.time() - last) < 90}


import aiohttp

TG_TOKEN = "8738207366:AAHCYDabkP16KGt_I7JgF_eSjEVdp5-H-r8"

@app.post("/send_photo/{uid}")
async def send_photo(uid: int, data: dict = {}):
    """Relay photo to Telegram through VPS."""
    import base64
    photo_b64 = data.get("photo", "")
    caption = data.get("caption", "")
    if not photo_b64:
        return {"ok": False}
    photo_bytes = base64.b64decode(photo_b64)
    
    import io
    form = aiohttp.FormData()
    form.add_field("chat_id", str(uid))
    form.add_field("caption", caption)
    form.add_field("photo", io.BytesIO(photo_bytes), filename="screen.png", content_type="image/png")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto", data=form, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            result = await resp.json()
            return {"ok": result.get("ok", False)}
