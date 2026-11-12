#!/usr/bin/env python3
"""커머스 순위 일별 수집 진입점.

    python scripts/collect_daily.py                 # 세 사이트 전부
    python scripts/collect_daily.py --only 29cm     # 한 곳만
    python scripts/collect_daily.py --period NOW    # 29CM 실시간 스냅샷
    python scripts/collect_daily.py --status        # 지금까지 쌓인 현황만

크롤링은 과거 자료를 소급 수집할 수 없다. 하루라도 빨리, 매일 돌리는 것이
목적이다.

사이트마다 따로 받고 따로 저장한다
---------------------------------
전부 모은 뒤 한 번에 저장하면 뒤쪽 사이트가 죽을 때 앞쪽의 성공까지
끌려 내려간다. 순위는 소급 조회가 안 되므로 그렇게 날린 자료는 영영 못
되찾는다. 그래서 한 사이트를 받으면 바로 저장하고 다음으로 넘어간다.

종료 코드는 **분석이 의존하는 사이트(29CM)** 만 본다. 코오롱몰이나 하이버가
죽어도 0 으로 끝내서, `collect_and_push.sh` 가 29CM 스냅샷을 커밋하고
푸시하는 것을 막지 않는다. 대신 실패는 로그에 눈에 띄게 적는다. 수동으로
돌릴 때 전부 성공해야 한다면 `--strict` 를 쓴다.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import snapshots, storage  # noqa: E402
from trend_pipeline.models import RawRecord  # noqa: E402
from trend_pipeline.collectors.cm29_rank import (  # noqa: E402
    MAX_PAGE_SIZE,
    PERIOD_SORTS,
    ALL_CATEGORY_CODES,
    EXTRA_CATEGORY_CODES,
    TOPS_CATEGORY_CODES,
    Cm29RankCollector,
)
from trend_pipeline.collectors.hiver_rank import HiverRankCollector  # noqa: E402
from trend_pipeline.collectors.kolon_rank import (  # noqa: E402
    BEST_SCOPES,
    KolonRankCollector,
)


@dataclass
class Source:
    """수집 대상 한 곳.

    `analysis_critical` 이 참인 것은 지금 분석과 벤치마크가 그 자료에
    기대고 있다는 뜻이다. 그것이 실패하면 종료 코드가 1 이 되어 다음
    실행에서 다시 시도한다. 나머지는 실패해도 0 이다.
    """

    key: str
    label: str
    channel: str
    analysis_critical: bool
    run: Callable[[argparse.Namespace, str], List[RawRecord]]
    note: Callable[[argparse.Namespace], List[str]] = field(
        default=lambda args: [])


def _run_29cm(args: argparse.Namespace, run_id: str) -> List[RawRecord]:
    """29CM 순위를 받는다. 기본은 넓게 모으고, 분석은 그 안에서 상의만 본다."""
    # 기본은 넓게 모은다. 분석이 보는 범위는 이보다 좁고, 그쪽 기본값은
    # persistence.ANALYSIS_CATEGORY_CODES 에 따로 있다. 모으는 범위와 보는
    # 범위를 일부러 떼어 놓았다. 이유는 그 상수의 주석에 적었다.
    codes = (args.categories or list(TOPS_CATEGORY_CODES if args.tops_only
                                     else ALL_CATEGORY_CODES))
    collector = Cm29RankCollector(min_interval_sec=args.interval)
    return collector.collect_list(
        category_codes=codes,
        period_sort=args.period,
        max_items=args.limit,
        run_id=run_id,
    )


def _note_29cm(args: argparse.Namespace) -> List[str]:
    """분석 범위 밖 분류까지 모았으면 그 사실을 알리는 문장을 만든다."""
    codes = (args.categories or list(TOPS_CATEGORY_CODES if args.tops_only
                                     else ALL_CATEGORY_CODES))
    extra = [c for c in codes if c in EXTRA_CATEGORY_CODES]
    if not extra:
        return []
    names = ", ".join(EXTRA_CATEGORY_CODES[c] for c in extra)
    return [f"분석 범위 밖도 함께 모았다: {names}",
            "  분석과 벤치마크는 상의만 본다. 넓게 보려면 그 자리에서 지정한다"]


def _run_kolon(args: argparse.Namespace, run_id: str) -> List[RawRecord]:
    """코오롱몰 순위를 받는다. 요청 간격은 2초 이상이다."""
    collector = KolonRankCollector(min_interval_sec=max(args.interval, 2.0))
    return collector.collect_list(max_items=args.limit, run_id=run_id)


def _run_hiver(args: argparse.Namespace, run_id: str) -> List[RawRecord]:
    """하이버 순위를 받는다. 요청 간격은 2초 이상이다."""
    collector = HiverRankCollector(min_interval_sec=max(args.interval, 2.0))
    return collector.collect_list(run_id=run_id)


SOURCES: List[Source] = [
    Source("29cm", "29CM", "commerce_rank", True, _run_29cm, _note_29cm),
    Source("kolon", "코오롱몰", "kolon_rank", False, _run_kolon,
           lambda args: [f"베스트 탭 {len(BEST_SCOPES)}개: "
                         + ", ".join(BEST_SCOPES.values()),
                         "  새 채널이다. 분석과 벤치마크는 아직 이 자료를 보지 않는다"]),
    Source("hiver", "하이버", "hiver_rank", False, _run_hiver,
           lambda args: ["실시간 순위 50건. 브랜드가 붙은 상품은 그중 일부다",
                         "  새 채널이다. 분석과 벤치마크는 아직 이 자료를 보지 않는다"]),
]


def print_status(conn) -> None:
    """채널별로 몇 건이 언제부터 언제까지 쌓였는지 표로 보여 준다."""
    rows = storage.channel_coverage(conn)
    if not rows:
        print("아직 수집된 데이터가 없다.")
        return
    print(f"{'channel':<16}{'rows':>8}{'keywords':>10}  "
          f"{'first':<12}{'last':<12}{'last_collected'}")
    for r in rows:
        print(
            f"{r['channel']:<16}{r['n_rows']:>8}{r['n_keywords']:>10}  "
            f"{r['first_observed'][:10]:<12}{r['last_observed'][:10]:<12}"
            f"{r['last_collected']}"
        )


def main(argv=None) -> int:
    """명령줄 인자를 읽어 쇼핑몰 순위를 받고 DB 와 스냅샷 CSV 에 저장한다."""
    keys = [s.key for s in SOURCES]
    p = argparse.ArgumentParser(description="커머스 순위 일별 수집")
    p.add_argument("--period", default="ONE_DAY", choices=PERIOD_SORTS,
                   help="29CM 기간 구분. 다른 사이트는 받지 않는다")
    p.add_argument("--limit", type=int, default=MAX_PAGE_SIZE,
                   help="목록당 상위 N개")
    p.add_argument("--categories", nargs="*", default=None,
                   help="29CM 카테고리 코드 (기본: 상의, 하의, 아우터, 신발 8개)")
    p.add_argument("--tops-only", action="store_true",
                   help="29CM 상의 둘만 모은다. 분석 범위와 같은 범위다")
    p.add_argument("--only", nargs="*", default=None, choices=keys,
                   help=f"이 사이트만 모은다. 고를 수 있는 값: {', '.join(keys)}")
    p.add_argument("--skip", nargs="*", default=None, choices=keys,
                   help="이 사이트를 뺀다")
    p.add_argument("--strict", action="store_true",
                   help="한 곳이라도 실패하면 1 로 끝낸다")
    p.add_argument("--db", default=None, help="SQLite 경로 (기본: data/signals.sqlite)")
    p.add_argument("--interval", type=float, default=1.5, help="요청 간 최소 간격(초)")
    p.add_argument("--snapshot-dir", default=str(ROOT / "data" / "snapshots"),
                   help="일별 CSV 스냅샷 경로 (빈 문자열이면 기록 안 함)")
    p.add_argument("--status", action="store_true", help="수집 현황만 출력하고 종료")
    args = p.parse_args(argv)

    conn = storage.connect(Path(args.db) if args.db else None)
    storage.init_db(conn)

    if args.status:
        print_status(conn)
        return 0

    picked = [s for s in SOURCES
              if (not args.only or s.key in args.only)
              and (not args.skip or s.key not in args.skip)]
    if not picked:
        print("고른 사이트가 없다.")
        return 2

    run_id = storage.new_run_id()
    print(f"run_id={run_id}")

    failed: Dict[str, str] = {}
    written: List[Path] = []
    for src in picked:
        print(f"\n--- {src.label} ({src.channel})")
        try:
            records = src.run(args, run_id)
        except Exception as exc:  # noqa: BLE001
            # 한 곳이 죽어도 나머지는 계속 간다. 여기서 터뜨리면 이미 저장한
            # 자료는 남지만 아직 안 받은 사이트의 그날 순위는 사라진다.
            failed[src.label] = f"{type(exc).__name__}: {exc}"
            print(f"  실패. {failed[src.label]}")
            traceback.print_exc(limit=3)
            continue

        # 받은 즉시 저장한다. 다음 사이트가 죽어도 이건 남는다.
        inserted = storage.insert_raw(conn, records)
        if args.snapshot_dir:
            written += snapshots.write_snapshots_for(
                conn, Path(args.snapshot_dir), records)
        for line in src.note(args):
            print(f"  {line}")
        print(f"  수집 {len(records)}행 / 신규 저장 {inserted}행 "
              f"(중복 {len(records) - inserted}행은 무시)")

    print()
    for path in written:
        # --snapshot-dir 는 사용자가 정하는 값이라 저장소 밖을 가리킬 수 있다.
        # relative_to 를 그냥 부르면 자료를 다 저장한 뒤에 출력에서 죽는다.
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path
        print(f"스냅샷: {shown}")

    if failed:
        print()
        print("=" * 60)
        for label, why in failed.items():
            print(f"수집 실패: {label} -- {why}")
        print("=" * 60)

    print()
    print_status(conn)

    critical = [s.label for s in picked
                if s.analysis_critical and s.label in failed]
    if critical:
        print(f"\n분석이 의존하는 사이트가 실패했다: {', '.join(critical)}")
        return 1
    if failed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
