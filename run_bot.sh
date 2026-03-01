#!/bin/bash
# Auto-restart bot if it crashes

while true; do
    echo "Starting bot..."
    cd /root/.openclaw/workspace/agents/itachi/night-leech
    python3 bot/night_leech_bot.py
    echo "Bot crashed with exit code $?. Restarting in 5 seconds..."
    sleep 5
done
