"""Local report viewer: serve only a fixed set of exported artifacts, never a directory."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def make_handler(run_dir):
    run_dir = Path(run_dir).resolve()
    allowed = {"/": "index.html", "/index.html": "index.html", "/suite.json": "suite.json", "/comparison.csv": "comparison.csv"}
    for case in ("01", "02", "03"):
        for name in ("report.html", "result.json", "metrics.csv"):
            allowed[f"/cases/{case}/{name}"] = f"cases/{case}/{name}"

    class ReportHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlsplit(self.path).path
            relative = allowed.get(route)
            if relative is None:
                self.send_error(404)
                return
            source = (run_dir / relative).resolve()
            if not source.is_relative_to(run_dir) or not source.is_file():
                self.send_error(404)
                return
            body = source.read_bytes()
            mime = {".html": "text/html", ".json": "application/json", ".csv": "text/csv"}[source.suffix]
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    return ReportHandler


def main():
    parser = argparse.ArgumentParser(description="Render only the saved PoC reports on localhost")
    parser.add_argument("--run-dir", type=Path, default=ROOT / "private/monthly-poc/2025-styles-v1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    if not (args.run_dir / "index.html").is_file():
        parser.error("Run scripts/monthly_poc.py report first")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.run_dir))
    print(f"PoC viewer: http://127.0.0.1:{server.server_port}/ (fixed report routes only)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
