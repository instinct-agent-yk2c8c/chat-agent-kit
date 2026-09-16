"""Shared helpers: a stub HTTP server that captures and answers requests."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class StubServer:
    """Records request (path, headers, body) and replies with a fixed body."""

    def __init__(self, response_body: dict, status: int = 200):
        self.requests: list[dict] = []
        self.response_body = response_body
        self.status = status

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                outer.requests.append({
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(body.decode()),
                })
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(outer.response_body).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
