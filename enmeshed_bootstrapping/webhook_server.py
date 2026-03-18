"""HTTP server processing connector webhooks."""

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer

_WEBHOOK_SRV_HOSTNAME = "localhost"
_WEBHOOK_SRV_PORT = 10001

# Function to handle connector webhooks, takes two arguments:
#  - the trigger (e.g. consumption.messageProcessed)
#  - a generic data map
type HandlerFn = Callable[[str, dict[str, object]], dict[str, object]]


def _make_handler(
    handlerfn: HandlerFn,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            result = {}
            length = int(self.headers["Content-Length"])
            body: dict[str, object] = json.loads(self.rfile.read(length))  # pyright: ignore[reportAny]

            trigger = body.pop("trigger")
            assert isinstance(trigger, str)
            if self.path == "/":
                result = handlerfn(trigger, body)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            _ = self.wfile.write(json.dumps(result).encode())

    return Handler


class WebhookServer:
    _server: HTTPServer

    def __init__(
        self,
        handlerfn: HandlerFn,
        hostname: str = _WEBHOOK_SRV_HOSTNAME,
        port: int = _WEBHOOK_SRV_PORT,
    ) -> None:
        self._server = HTTPServer((hostname, port), _make_handler(handlerfn))

    def serve_forever(self) -> None:
        self._server.serve_forever()
