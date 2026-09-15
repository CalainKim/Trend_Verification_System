#!/usr/bin/env python3
"""역추적 케이스 번들 생성.

    # 먼저 추이를 보고 T_peak 을 정한다
    python scripts/build_case.py --survey 럭비티 럭비셔츠

    # 정한 뒤 번들을 만든다
    python scripts/build_case.py \
        --case-id case_001_rugby --keyword 럭비티 --synonyms 럭비셔츠 \
        --t-peak 2024-09-15 --label real --reason "피크 후 1년간 지수 절반 이상 유지"

T_peak 은 자동으로 정하지 않는다. 무엇을 '폭발한 시점'으로 볼지는 연구자가
기준에 따라 판단할 문제이고, 그 판단이 케이스의 난이도를 결정한다.
스크립트가 조용히 정해버리면 근거가 남지 않는다.

수집은 전부 T_cut 이전으로 제한하고, 내보내기 직전에 한 번 더 검증한다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import config, export, storage  # noqa: E402
from trend_pipeline.collectors.naver_base import NaverApiError  # noqa: E402
from trend_pipeline.collectors.naver_datalab import NaverDataLabCollector  # noqa: E402
from trend_pipeline.collectors.naver_shopping import (  # noqa: E402
    TOPS_CATEGORIES,
    NaverShoppingCollector,
)
from trend_pipeline.models import utcnow_iso  # noqa: E402

#: T_cut 은 T_peak 에서 이만큼 앞선 시점. 재고 대응에 필요한 선행 시간이다.
LEAD_WEEKS = 4
#: T_cut 이전 몇 년치를 모을지. 계절성을 보려면 최소 2년은 있어야 한다.
HISTORY_YEARS = 3


def survey(keyword: str, synonyms) -> int:
    """월별 추이를 출력해 T_peak 판단을 돕는다."""
    cid, secret = config.naver_credentials()
    c = NaverDataLabCollector(cid, secret, min_interval_sec=0.3)
    rows = list(c.collect({keyword: [keyword, *synonyms]},
                          "2016-01-01", date.today().isoformat(), time_unit="month"))
    print(f"{keyword} 월별 상대 지수 (이 요청 안에서만 비교 가능)\n")
    for r in rows:
        if r.metric_value < 0.5:
            continue
        print(f"  {r.observed_at[:7]}  {r.metric_value:>6.1f}  {'█' * int(r.metric_value / 2)}")
    peak = max(rows, key=lambda r: r.metric_value)
    print(f"\n  최고점 {peak.observed_at[:7]} ({peak.metric_value})")
    print("  이 값만 보고 T_peak 을 정하지 말 것. 어느 시점을 '폭발'로 볼지는")
    print("  합의된 기준에 따라 판단하고 그 근거를 --reason 에 남긴다.")
    return 0


def build(args) -> int:
    t_peak = date.fromisoformat(args.t_peak)
    t_cut = t_peak - timedelta(weeks=args.lead_weeks)
    start = t_cut - timedelta(days=365 * args.history_years)
    # 수집 상한은 T_cut 하루 전. T_cut 당일도 넣지 않는다.
    end = t_cut - timedelta(days=1)

    print(f"케이스   {args.case_id}")
    print(f"키워드   {args.keyword} {list(args.synonyms) or ''}")
    print(f"T_peak   {t_peak}")
    print(f"T_cut    {t_cut}   (T_peak - {args.lead_weeks}주)")
    print(f"수집구간 {start} ~ {end}\n")

    cid, secret = config.naver_credentials()
    conn = storage.connect()
    storage.init_db(conn)
    run_id = storage.new_run_id()
    keywords = [args.keyword, *args.synonyms]

    search = NaverDataLabCollector(cid, secret, min_interval_sec=0.3)
    total = 0

    recs = list(search.collect({args.keyword: keywords}, start.isoformat(),
                               end.isoformat(), run_id=run_id))
    total += storage.insert_raw(conn, recs)
    print(f"  검색어 트렌드            {len(recs):>5}행")

    for gender in ("f", "m"):
        recs = list(search.collect({args.keyword: keywords}, start.isoformat(),
                                   end.isoformat(), gender=gender, run_id=run_id))
        total += storage.insert_raw(conn, recs)
        print(f"  검색어 트렌드 (성별 {gender})   {len(recs):>5}행")

    if args.shopping_category:
        shop = NaverShoppingCollector(cid, secret, min_interval_sec=0.3)
        try:
            # 쇼핑인사이트는 그룹당 표현 1개만 받는다. 동의어는 그룹을 나눈다.
            recs = list(shop.collect_keyword(args.shopping_category,
                                             {k: [k] for k in keywords},
                                             start.isoformat(), end.isoformat(), run_id=run_id))
            total += storage.insert_raw(conn, recs)
            print(f"  쇼핑 클릭 추이           {len(recs):>5}행")
            recs = list(shop.collect_keyword_demographics(
                args.shopping_category, args.keyword,
                start.isoformat(), end.isoformat(), run_id=run_id))
            total += storage.insert_raw(conn, recs)
            print(f"  쇼핑 성별·연령 분해       {len(recs):>5}행")
        except NaverApiError as exc:
            print(f"  쇼핑인사이트 실패: {exc}")

    print(f"\n  신규 저장 {total}행")

    conn.execute(
        "INSERT OR REPLACE INTO trend_case"
        "(case_id, keyword, t_peak, t_cut, label, label_reason, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (args.case_id, args.keyword, t_peak.isoformat(), t_cut.isoformat(),
         args.label, args.reason, utcnow_iso()),
    )
    conn.commit()
    print(f"  trend_case 에 정답 기록 (label={args.label}) - 산출물에는 넣지 않는다")

    case = export.TrendCase(args.case_id, args.keyword, t_peak.isoformat(),
                            t_cut.isoformat(), args.label, args.reason)
    out = export.write_case_bundle(conn, case, ROOT / "cases", keywords=[args.keyword])
    print(f"\n번들 생성 {out.relative_to(ROOT)}")
    for f in sorted(out.iterdir()):
        print(f"  {f.name:<24} {f.stat().st_size:>7,} bytes")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="역추적 케이스 번들 생성")
    p.add_argument("--survey", nargs="+", metavar="KEYWORD",
                   help="추이만 출력하고 종료 (첫 값이 대표어)")
    p.add_argument("--case-id")
    p.add_argument("--keyword")
    p.add_argument("--synonyms", nargs="*", default=[])
    p.add_argument("--t-peak", help="YYYY-MM-DD")
    p.add_argument("--label", choices=["real", "noise"])
    p.add_argument("--reason", default="", help="이 라벨을 붙인 근거")
    p.add_argument("--shopping-category", default=None,
                   choices=list(TOPS_CATEGORIES) + [None])
    p.add_argument("--lead-weeks", type=int, default=LEAD_WEEKS)
    p.add_argument("--history-years", type=int, default=HISTORY_YEARS)
    args = p.parse_args(argv)

    if args.survey:
        return survey(args.survey[0], args.survey[1:])
    missing = [f for f in ("case_id", "keyword", "t_peak", "label")
               if not getattr(args, f)]
    if missing:
        p.error(f"필수 인자 누락: {', '.join('--' + m.replace('_', '-') for m in missing)}")
    if not args.reason:
        p.error("--reason 은 비워둘 수 없다. 라벨 근거가 없으면 케이스를 재현·검토할 수 없다")
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
