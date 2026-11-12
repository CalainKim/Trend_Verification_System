"""Report boundaries: archived tasks and source text cannot become active UI."""
import importlib.util
import json
import hashlib
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_separates_old_tasks_and_escapes_source_html(tmp_path):
    new = tmp_path / "runs/new"
    old = tmp_path / "runs/old"
    new.mkdir(parents=True)
    old.mkdir()
    raw = '</script><script>alert("injected")</script>'
    record = {"schema_version": "candidate-verification-v1", "case": {"title": raw}, "artifacts": {}}
    record["record_sha256"] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (new / "run.json").write_text(json.dumps(record), encoding="utf-8")
    (old / "run.json").write_text(json.dumps({"schema_version": "forecast-v2", "private_old_task": True}), encoding="utf-8")
    result = load_script("build_candidate_report").build_report(tmp_path / "runs", tmp_path / "report")
    text = result.read_text(encoding="utf-8")
    payload = text.split('<script id="records" type="application/json">')[1].split('</script>')[0]
    assert json.loads(payload)[0]["case"]["title"] == raw
    assert "<script>" not in payload
    assert "private_old_task" not in payload
    record["case"]["title"] = "tampered"
    (new / "run.json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        load_script("build_candidate_report").build_report(tmp_path / "runs", tmp_path / "report")


def test_server_does_not_expose_run_files_or_other_local_files(tmp_path):
    module = load_script("serve_candidate_report")
    (tmp_path / "index.html").write_text("<h1>report</h1>", encoding="utf-8")
    (tmp_path / "secret.json").write_text("private", encoding="utf-8")
    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.make_handler(tmp_path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base) as response:
            assert response.read() == b"<h1>report</h1>"
            assert "connect-src 'none'" in response.headers["Content-Security-Policy"]
        for path in ("/secret.json", "/../secret.json", "/api/complete"):
            with pytest.raises(HTTPError) as failure:
                urlopen(base + path)
            assert failure.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
