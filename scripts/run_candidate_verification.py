#!/usr/bin/env python3
"""Run an offline demo or a hash-bound live arm with cumulative reservations."""
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
    sub.add_parser("budget-audit", help="Read historical budgets without initializing a new ledger")
    status = sub.add_parser("budget-status", help="Check cumulative ledger and reconcile stopped GPU evidence")
    live = sub.add_parser("live", help="One authorized arm, no automatic retries")
    for command in (status, live):
        command.add_argument("--authorization", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
    live.add_argument("--case", type=Path, required=True)
    live.add_argument("--corpus", type=Path, required=True)
    live.add_argument("--criteria", type=Path, required=True)
    live.add_argument("--model", choices=("claude", "qwen"), required=True)
    live.add_argument("--condition", choices=("with_interview", "without_interview"), required=True)
    live.add_argument("--output-dir", type=Path, default=ROOT / "private/candidate-live/runs")
    live.add_argument("--credentials-root", type=Path, default=ROOT)
    live.add_argument("--diagnostic-from", type=Path,
                      help="One explicitly authorized manual diagnostic of the matching failed Qwen interview arm")
    args = parser.parse_args(argv)
    if args.command is None:
        args = parser.parse_args(["demo"])
    try:
        if args.command == "budget-audit":
            from trend_verification_v1.live import audit_prior
            result = audit_prior(ROOT)
        elif args.command in ("live", "budget-status"):
            from trend_verification_v1.live import LiveLedger, run_live
            authorization = unique_json(args.authorization.read_text(encoding="utf-8-sig"))
            config = unique_json(args.config.read_text(encoding="utf-8-sig"))
            if args.command == "budget-status":
                result = LiveLedger(ROOT, authorization, config).status()
            else:
                inputs = [unique_json(path.read_text(encoding="utf-8-sig"))
                          for path in (args.case, args.corpus, args.criteria)]
                record = run_live(*inputs, root=ROOT, authorization=authorization, config=config,
                                  model_name=args.model, condition=args.condition,
                                  output_dir=args.output_dir, credentials_root=args.credentials_root,
                                  diagnostic_from=args.diagnostic_from)
                result = {"run_id": record["run_id"], "status": record["status"],
                          "synthetic": record["synthetic"], "execution_kind": record["model"]["execution_kind"],
                          "verdict": record["final"]["verdict"] if record["final"] else None,
                          "path": str(args.output_dir / record["run_id"] / "run.json")}
        elif args.command == "inspect-config":
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
        if args.command == "live":
            return 0 if result["status"] == "complete" else 1
        return 0 if args.command != "demo" or all(r["status"] == "complete" for r in records) else 1
    except (ValueError, RuntimeError, OSError, TypeError) as exc:
        print(json.dumps({"status": "configuration_error", "error_type": type(exc).__name__,
                          "message": "Input/configuration/budget/integrity check failed; inspect immutable run and budget records"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
