#!/usr/bin/env python3
"""트랙 B 일별 수집 진입점.

    python scripts/collect_daily.py                 # 상의 카테고리 일간 랭킹 100위
    python scripts/collect_daily.py --period NOW    # 실시간 랭킹 스냅샷
    python scripts/collect_daily.py --status        # 지금까지 쌓인 현황만 출력

크롤링은 과거 데이터를 소급 수집할 수 없다. 하루라도 빨리, 매일 돌리는 것이 목적이다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import snapshots, storage  # noqa: E402
from trend_pipeline.collectors.cm29_rank import (  # noqa: E402
    MAX_PAGE_SIZE,
    PERIOD_SORTS,
    TOPS_CATEGORY_CODES,
    Cm29RankCollector,
)


def print_status(conn) -> None:
    rows = storage.channel_coverage(conn)
    if not rows:
        print("아직 수집된 데이터가 없다.")
        return
    print(f"{'channel':<16}{'rows':>8}{'keywords':>10}  {'first':<12}{'last':<12}{'last_collected'}")
    for r in rows:
        print(
            f"{r['channel']:<16}{r['n_rows']:>8}{r['n_keywords']:>10}  "
            f"{r['first_observed'][:10]:<12}{r['last_observed'][:10]:<12}{r['last_collected']}"
        )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="29CM 베스트 랭킹 일별 수집")
    p.add_argument("--period", default="ONE_DAY", choices=PERIOD_SORTS)
    p.add_argument("--limit", type=int, default=MAX_PAGE_SIZE, help="카테고리당 상위 N개")
    p.add_argument("--categories", nargs="*", default=None, help="카테고리 코드 (기본: 상의)")
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

    codes = args.categories or list(TOPS_CATEGORY_CODES)
    collector = Cm29RankCollector(min_interval_sec=args.interval)
    run_id = storage.new_run_id()

    records = collector.collect_list(
        category_codes=codes,
        period_sort=args.period,
        max_items=args.limit,
        run_id=run_id,
    )
    inserted = storage.insert_raw(conn, records)
    written = (
        snapshots.write_snapshots_for(conn, Path(args.snapshot_dir), records)
        if args.snapshot_dir else []
    )

    print(f"run_id={run_id}")
    print(f"카테고리 {len(codes)}개 · 수집 {len(records)}행 · 신규 저장 {inserted}행 "
          f"(중복 {len(records) - inserted}행은 무시)")
    for path in written:
        print(f"스냅샷: {path.relative_to(ROOT)}")
    print_status(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
