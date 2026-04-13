#!/bin/bash
cd /root/gta5rp_helper

# API
pkill -f "api_server:app.*7755" 2>/dev/null
sleep 1
uvicorn api_server:app --host 127.0.0.1 --port 7755 >> api.log 2>&1 &
sleep 2

# Bot with auto-restart
while true; do
    python3 -u bot.py >> bot.log 2>&1
    echo "[$(date)] Restarting..." >> bot.log
    # Restart API if dead
    curl -s http://127.0.0.1:7755/heartbeat/0 > /dev/null || {
        uvicorn api_server:app --host 127.0.0.1 --port 7755 >> api.log 2>&1 &
        sleep 2
    }
    sleep 3
done
