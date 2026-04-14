#!/usr/bin/env python3
"""
Simple web server for Binance UI
Serves HTML and proxies API requests
"""

import http.server
import socketserver
import urllib.request
import json
from pathlib import Path

PORT = 8080
API_PORT = 5000

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent / "web"), **kwargs)
    
    def do_GET(self):
        # Proxy API requests to Flask server
        if self.path.startswith('/api/'):
            try:
                url = f'http://localhost:{API_PORT}{self.path}'
                with urllib.request.urlopen(url) as response:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(response.read())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            # Serve static files
            super().do_GET()

if __name__ == '__main__':
    print(f"🌐 Web UI Server starting on http://localhost:{PORT}")
    print(f"   Proxying API to localhost:{API_PORT}")
    print(f"   Open: http://localhost:{PORT}")
    print()
    
    with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
        httpd.serve_forever()
