"""Tiny stand-in for hermes-adapter used by the provisioner test: serves
GET /health -> 200 on the workspace port and holds a socket on the A2A port, so
the LocalDockerProvisioner's real deploy/health/recycle path is exercised without
pulling the heavy real image. Prod swaps in hermes-adapter via HERMES_ADAPTER_IMAGE
(same code path)."""

import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

WS_PORT = int(os.environ.get("HERMES_ADAPTER_PORT", "8766"))
A2A_PORT = int(os.environ.get("A2A_PORT", "9000"))


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *a):
        pass


def _hold_a2a():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", A2A_PORT))
    s.listen(8)
    while True:
        conn, _ = s.accept()
        conn.close()


threading.Thread(target=_hold_a2a, daemon=True).start()
HTTPServer(("0.0.0.0", WS_PORT), H).serve_forever()
