"""Minimal local receiver for the alert engine's webhook/Slack dispatch.

Stdlib only, no dependencies. Prints every POST body it receives so you can
watch an alert actually leave the system, not just appear in the DB/API -
see docs/DEMO.md for the full walkthrough.

Usage:
    python scripts/dev_webhook_receiver.py [--port 8099]

Then, with the lite stack up, point the alert engine at it and restart the
backend to pick up the new .env values (Settings is cached per-process):

    # .env - reachable from inside the backend container on Docker Desktop
    ALERT_WEBHOOK_URL=http://host.docker.internal:8099/webhook
    SLACK_WEBHOOK_URL=http://host.docker.internal:8099/slack

    docker compose up -d backend

Not for production - it has no auth and does nothing with what it receives
beyond printing it.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


def format_received(path: str, body: bytes) -> str:
    """Pure formatting, split out from the handler so it's unit-testable
    without spinning up a real HTTP server."""
    try:
        parsed = json.dumps(json.loads(body), indent=2)
    except json.JSONDecodeError:
        parsed = body.decode(errors="replace")
    return f"[webhook] POST {path}\n{parsed}"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - stdlib dispatches on this exact name
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        print(format_received(self.path, body), flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass  # silence the default per-request access log; we print our own


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    print(f"Listening on http://0.0.0.0:{args.port} - Ctrl+C to stop")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
