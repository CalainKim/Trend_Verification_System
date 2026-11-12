"""Local report viewer: serve only a fixed set of exported artifacts, never a directory."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def make_handler(run_dir):
    """저장된 보고서 파일만 내보내는 웹 서버 처리기를 만든다. 목록에 없는 주소는 404 다."""
    run_dir = Path(run_dir).resolve()
    allowed = {"/": "index.html", "/index.html": "index.html", "/suite.json": "suite.json", "/comparison.csv": "comparison.csv"}
    for case in ("01", "02", "03"):
        for name in ("report.html", "result.json", "metrics.csv"):
            allowed[f"/cases/{case}/{name}"] = f"cases/{case}/{name}"

    class ReportHandler(BaseHTTPRequestHandler):
        """허용한 보고서 파일만 돌려주는 요청 처리기다."""
        def do_GET(self):
            """주소가 허용 목록에 있으면 그 파일을 돌려주고, 아니면 404 를 돌려준다."""
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
            """요청마다 찍히는 기록을 끈다."""
            pass

    return ReportHandler


def main():
    """월간 사례 보고서를 내 컴퓨터(localhost)에서 열어 볼 수 있게 띄운다."""
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
