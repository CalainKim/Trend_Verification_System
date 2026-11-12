"""Build a self-contained, offline viewer from candidate-verification-v1 runs.

The viewer never calls a model or changes a saved judgment. Its input is the
immutable run.json produced by run_candidate_verification.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_verification_v1.engine import verify_run


def build_report(runs_dir: Path, output_dir: Path) -> Path:
    records = []
    for source in sorted(runs_dir.rglob("run.json")):
        record = json.loads(source.read_text(encoding="utf-8"))
        if record.get("schema_version") != "candidate-verification-v1":
            continue
        records.append(verify_run(source.parent))
    if not records:
        raise ValueError("No candidate-verification-v1 run.json records found")
    # Escape HTML delimiters even inside JSON strings; all dynamic DOM text is
    # assigned using textContent rather than interpreting source text as HTML.
    payload = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("&", "\\u0026")
    template = (ROOT / "web/candidate-verification.html").read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "index.html"
    destination.write_text(template.replace("__RUN_RECORDS__", payload), encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "private/candidate-verification")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "private/candidate-report")
    args = parser.parse_args()
    print(build_report(args.runs_dir.resolve(), args.output_dir.resolve()))


if __name__ == "__main__":
    main()
