"""Serve only the exported candidate report on localhost; no model endpoints."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def make_handler(report_dir):
    report = Path(report_dir).resolve() / "index.html"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path not in ("/", "/index.html") or not report.is_file():
                self.send_error(404)
                return
            body = report.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "private/candidate-report")
    parser.add_argument("--port", type=int, default=8774)
    args = parser.parse_args()
    if not (args.report_dir / "index.html").is_file():
        parser.error("Build the report with scripts/build_candidate_report.py first")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.report_dir))
    print(f"Candidate viewer: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
