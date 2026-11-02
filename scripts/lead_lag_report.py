#!/usr/bin/env python3
"""해외 선행 일수를 키워드별로 출력한다.

    python scripts/lead_lag_report.py
    python scripts/lead_lag_report.py --geo WORLD --as-of 2026-11-01

연구계획서의 "유행은 주로 해외에서 한국으로 온다" 는 가설을 전제로 쓰지 않고
자료로 확인하기 위한 보고다. 해외 시계열을 날짜 단위로 밀어 가며 국내와 가장
잘 겹치는 지점을 찾는다.

문턱에 미달한 결과도 함께 보여 준다. 통과한 것만 보이면 몇 개를 걸러냈는지
알 수 없고, 그러면 통과한 결과가 실제보다 강해 보인다.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from trend_pipeline import features as ft, storage  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="해외 선행 일수 보고")
    p.add_argument("--db", default=None)
    p.add_argument("--geo", default="US", help="한국과 견줄 지역")
    p.add_argument("--as-of", default=None, help="기본값은 오늘")
    p.add_argument("--window", type=int, default=1500, help="분석 구간 일수")
    p.add_argument("--gprop", default="", help="빈 값은 웹 검색, youtube 도 가능")
    args = p.parse_args(argv)

    import collect_gtrends as cg
    from trend_pipeline.models import utcnow_iso

    conn = storage.connect(Path(args.db) if args.db else None)
    conn.row_factory = sqlite3.Row
    as_of = args.as_of or utcnow_iso()[:10]
    keywords = sorted(cg.already_have(conn, "gtrends", args.gprop))
    if not keywords:
        print("수집된 키워드가 없다.")
        return 1

    print(f"해외 선행 분석  탐색 범위 {ft.MAX_LEAD_DAYS}일, "
          f"신뢰 문턱 상관 {ft.MIN_LEAD_CORRELATION}")
    print(f"기준 시점 {as_of}, 분석 구간 {args.window}일, 비교 지역 {args.geo}")
    print()
    print(f"{'속성':<12}{'선행일수':>8}{'상관':>8}{'겹침':>7}   판정")

    leads = []
    for kw in keywords:
        try:
            r = ft.lead_lag(conn, kw, as_of, args.geo,
                            window_days=args.window, gprop=args.gprop)
        except ft.MixedQueryWindow:
            print(f"{kw:<12}{'-':>8}{'-':>8}{'-':>7}   정규화 창 혼합")
            continue
        if r is None:
            print(f"{kw:<12}{'-':>8}{'-':>8}{'-':>7}   자료 부족")
            continue
        if not r.reliable:
            why = "경계" if r.at_boundary else "문턱 미달"
            print(f"{kw:<12}{'-':>8}{r.correlation:>8.2f}{r.n_overlap:>7}   {why}")
            continue
        side = "한국 선행" if r.lead_days < 0 else "해외 선행"
        print(f"{kw:<12}{r.lead_days:>8}{r.correlation:>8.2f}"
              f"{r.n_overlap:>7}   {side}")
        leads.append(r.lead_days)

    print()
    if leads:
        home = sum(1 for d in leads if d < 0)
        print(f"신뢰 가능 {len(leads)}건 중 한국 선행 {home}건, "
              f"해외 선행 {len(leads) - home}건")
        print("표본이 작고 계절성을 분리하지 못했으므로 이 수치만으로 "
              "가설을 반박하지 않는다.")
    else:
        print("신뢰 문턱을 넘은 결과가 없다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
