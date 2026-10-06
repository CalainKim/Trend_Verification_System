"""Real monthly observations -> one fixed API judgment -> later observations."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_poc.monthly import MonthlyService
from trend_poc.naver import NaverError


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="3월 대비 4월 선정 이유 → 고정 AI 판단 → 5~10월 월별 관측")
    parser.add_argument("command", choices=["prepare", "collect", "review", "retry-review", "evaluate", "report", "run", "status", "audit"])
    parser.add_argument("--run-dir", type=Path, default=ROOT / "private/monthly-poc/2025-styles-v1")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/cases/monthly-2025.json")
    parser.add_argument("--provider", choices=["developers", "cloud"], default="cloud")
    parser.add_argument("--case", type=int, choices=[1, 2, 3], help="명시적 실패 재검토 대상. 1회 추가 유료 호출")
    args = parser.parse_args()
    service = MonthlyService(ROOT, args.run_dir, args.manifest, provider=args.provider)
    try:
        if args.command == "run":
            service.collect()
            review = service.review()
            if review["status"] == "complete":
                service.evaluate()
            service.export()
            if review["status"] != "complete":
                print(json.dumps(service.status(), ensure_ascii=False, indent=2))
                return 1
        elif args.command == "retry-review":
            if args.case is None:
                raise ValueError("재검토할 사례 --case 1|2|3을 지정하세요.")
            service.retry_review(args.case - 1)
        elif args.command == "report":
            service.export()
        elif args.command == "audit":
            service.verify_complete()
            print(json.dumps({"status": "verified", "network_calls": 0}, ensure_ascii=False))
            return 0
        elif args.command != "status":
            getattr(service, args.command)()
        print(json.dumps(service.status(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, (NaverError, ValueError)) else type(exc).__name__ + ": 실행 기록을 확인하세요."
        print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
        return 1
    finally:
        if service.naver is not None and hasattr(service.naver, "close"):
            service.naver.close()


if __name__ == "__main__":
    raise SystemExit(main())
