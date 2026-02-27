#!/bin/bash
# Auto-restart file server if it crashes

while true; do
    echo "Starting file server..."
    cd /root/.openclaw/workspace/agents/itachi/night-leech
    python3 file_server.py
    echo "File server crashed, restarting in 2 seconds..."
    sleep 2
done
