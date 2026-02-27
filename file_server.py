#!/usr/bin/env python3
# Simple File Server for Downloads

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

PORT = 8084
DIRECTORY = "/root/Downloads"

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        pass  # Disable logging

print(f"Starting file server on port {PORT}")
print(f"Serving files from: {DIRECTORY}")

server = HTTPServer(('0.0.0.0', PORT), Handler)
server.serve_forever()
