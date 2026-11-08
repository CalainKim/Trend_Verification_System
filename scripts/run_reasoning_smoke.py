#!/usr/bin/env python3
"""Run the budget-limited sweatshirt research pilot without a product website."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_research.inputs import PROMPT_VERSIONS, build_prompt, load_cases, load_manifest, prepare_case
from trend_research.runner import DEFAULT_CONFIG, atomic_json, export_run, freeze, run, score_run
from trend_research.providers import ProviderError


def main(argv=None):
    parser = argparse.ArgumentParser(description="맨투맨 8건: 입력 분리, 추론, 봉인, 예비 채점")
    parser.add_argument("command", choices=["preview", "run", "export", "freeze", "score"])
    parser.add_argument("--provider", choices=["claude", "a40", "both"], default="both")
    parser.add_argument("--input-view", choices=["static", "history", "structured"], default="structured")
    parser.add_argument("--prompt-version", choices=PROMPT_VERSIONS, default="pilot-v1",
                        help="기존 pilot-v1 또는 예측/HOLD 구분을 명시한 forecast-v2; 버전별 store 분리")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--credentials-root", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, help="처음 N개 사례. 같은 store에서 이어 실행하면 완료 결과 재사용")
    parser.add_argument("--retry", action="store_true", help="실패한 요청만 재시도. 전체 최대 4회")
    parser.add_argument("--demo", action="store_true", help="네트워크 없는 합성 응답. 실제 결과와 별도 저장")
    parser.add_argument("--labels", type=Path, help="freeze 후에만 봉인 정답 읽기 허용")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    store = args.store or ROOT / "private/research-pilot" / ("demo" if args.demo else "live")
    try:
        if args.command == "preview":
            manifest = load_manifest(args.manifest, repo_root=ROOT)
            cases = load_cases(manifest, ROOT)
            prepared = [prepare_case(x, args.input_view) for x in cases[:args.limit]]
            data = {"model_calls": 0, "input_view": args.input_view, "prompt_version": args.prompt_version, "cases": prepared,
                    "prompts": [{"case_id": p["case_id"], "system": build_prompt(p, args.prompt_version)[0],
                                 "user": build_prompt(p, args.prompt_version)[1]} for p in prepared]}
            if args.output_dir:
                atomic_json(args.output_dir / f"preview-{args.input_view}.json", data)
                result = {"model_calls": 0, "cases": len(prepared), "output_dir": str(args.output_dir.resolve())}
            else:
                result = data
        elif args.command == "run":
            state = run(store, repo_root=ROOT, manifest_path=args.manifest, config_path=args.config,
                        provider=args.provider, input_view=args.input_view, credentials_root=args.credentials_root,
                        limit=args.limit, retry=args.retry, demo=args.demo, prompt_version=args.prompt_version)
            result = {"store": str(store.resolve()), "demo": state["demo"], "attempts": len(state["attempts"]),
                      "claude_accounted_usd": sum(a["accounted_claude_usd"] for a in state["attempts"]),
                      "records": [{k: r.get(k) for k in ("case_id", "provider", "input_view", "status", "error", "validation_errors")}
                                  for r in state["records"].values()]}
        elif args.command == "freeze":
            snapshot = freeze(store)
            result = {"frozen_at": snapshot["frozen_at"], "prediction_sha256": snapshot["prediction_sha256"]}
        elif args.command == "score":
            if args.labels is None:
                parser.error("score에는 --labels가 필요합니다. 먼저 freeze를 실행하세요.")
            result = score_run(store, args.labels)
        else:
            result = export_run(store, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, ProviderError, KeyError) as exc:
        # No HTTP response bodies, credentials, or resolved secret values.
        print(f"실험 중단: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
