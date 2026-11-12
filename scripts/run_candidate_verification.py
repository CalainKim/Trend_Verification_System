#!/usr/bin/env python3
"""Run the explicitly synthetic offline demo, inspect configuration, or verify records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_verification_v1.demo import load_example
from trend_verification_v1.engine import inspect_live_config, run_case, verify_run
from trend_verification_v1.inputs import unique_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    demo = sub.add_parser("demo", help="Four synthetic slots; no actual Claude/Qwen call")
    demo.add_argument("--output-dir", type=Path, default=ROOT / "private/candidate-verification")
    demo.add_argument("--model", choices=("claude", "qwen", "all"), default="all")
    demo.add_argument("--condition", choices=("with_interview", "without_interview", "all"), default="all")
    inspect = sub.add_parser("inspect-config", help="Validate settings; live execution remains locked")
    inspect.add_argument("--config", type=Path, default=ROOT / "configs/candidate-verification.example.json")
    verify = sub.add_parser("verify", help="Verify a run record and every frozen artifact")
    verify.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    if args.command is None:
        args = parser.parse_args(["demo"])
    try:
        if args.command == "inspect-config":
            result = inspect_live_config(unique_json(args.config.read_text(encoding="utf-8-sig")))
        elif args.command == "verify":
            record = verify_run(args.run_dir)
            result = {"run_id": record["run_id"], "integrity": "verified", "status": record["status"]}
        else:
            case, corpus, criteria = load_example(ROOT)
            models = ("claude", "qwen") if args.model == "all" else (args.model,)
            conditions = ("with_interview", "without_interview") if args.condition == "all" else (args.condition,)
            records = [run_case(case, corpus, criteria, model_name=model, condition=condition,
                                output_dir=args.output_dir) for model in models for condition in conditions]
            result = {"synthetic": True, "actual_model_calls": 0, "study_cases": 0,
                      "runs": [{"run_id": r["run_id"], "model_slot": r["model"]["comparison_slot"],
                                "condition": r["condition"], "status": r["status"],
                                "verdict": r["final"]["verdict"] if r["final"] else None,
                                "path": str(args.output_dir / r["run_id"] / "run.json")} for r in records]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command != "demo" or all(r["status"] == "complete" for r in records) else 1
    except (ValueError, RuntimeError, OSError, TypeError) as exc:
        print(json.dumps({"status": "configuration_error", "error_type": type(exc).__name__,
                          "message": "Input/configuration/integrity check failed; no live calls were authorized"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
