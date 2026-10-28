#!/usr/bin/env python3
"""구글 트렌드 수집. 지역마다 현지 질의어를 쓴다.

    python scripts/collect_gtrends.py --plan                 # 질의 계획만 출력
    python scripts/collect_gtrends.py --limit 10             # 상위 10개 수집
    python scripts/collect_gtrends.py --props web youtube    # 속성 두 가지

무신사가 제시한 가설은 "유행은 주로 해외에서 한국으로 온다" 이다. 이를
검증하려면 지역마다 다른 단어를 물어야 한다. 미국에 "맨투맨" 을 물으면
현지 유행이 아니라 한국어 사용자의 검색을 재게 된다. 그래도 숫자는 멀쩡히
나오므로 틀린 줄 모른 채 가설을 검증했다고 착각한다. 실제로 그렇게 쌓인
자료가 있었고(맨투맨 geo=US), 한국이 35일 앞선다는 결과가 나왔다.
질의어를 지역별로 나누는 것이 이 스크립트의 존재 이유다.

질의어 매핑은 data/attributes.yml 의 canonical 과 en 에서 가져온다.
en 이 없는 속성은 해외 비교에서 제외한다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import storage  # noqa: E402
from trend_pipeline.collectors.gtrends import (  # noqa: E402
    GoogleTrendsCollector,
    GoogleTrendsUnavailable,
)
from trend_pipeline.models import geo_entity  # noqa: E402
from trend_pipeline.models import utcnow_iso  # noqa: E402

DICT_PATH = ROOT / "data" / "attributes.yml"
MAP_PATH = ROOT / "data" / "attribute_map.csv"

#: 한국 대비 비교 대상. 빈 문자열은 전세계다.
GEOS = ("KR", "US", "")

PROP_ALIASES = {"web": "", "youtube": "youtube"}


def load_terms(limit: Optional[int]) -> List[Dict[str, str]]:
    """해외 질의어가 있는 속성을 커머스 노출이 많은 순으로 고른다.

    노출 순으로 자르는 이유가 있다. 쿼터가 넉넉하지 않고 한 속성마다
    지역 세 번씩 묻기 때문에, 커머스에서 실제로 보이지 않는 속성부터
    묻기 시작하면 정작 필요한 것에 도달하기 전에 막힌다.
    """
    raw = yaml.safe_load(DICT_PATH.read_text(encoding="utf-8"))
    pairs = {a["canonical"]: a["en"] for a in raw["attributes"] if a.get("en")}

    freq: Counter = Counter()
    if MAP_PATH.exists():
        for row in csv.DictReader(MAP_PATH.open(encoding="utf-8")):
            freq[row["attribute"]] += 1

    terms = [{"ko": ko, "en": en, "n": freq.get(ko, 0)} for ko, en in pairs.items()]
    terms.sort(key=lambda t: (-t["n"], t["ko"]))
    return terms[:limit] if limit else terms


def print_plan(terms, geos, props, start, end) -> None:
    n_req = len(terms) * len(geos) * len(props)
    print(f"질의 계획: 속성 {len(terms)}개 x 지역 {len(geos)}개 x 속성값 {len(props)}개 "
          f"= {n_req}회")
    print(f"기간 {start} ~ {end}")
    print(f"요청 간격 {GoogleTrendsCollector.min_interval_sec}초 이상이므로 "
          f"최소 {n_req * GoogleTrendsCollector.min_interval_sec / 60:.0f}분 걸린다\n")
    print(f"{'속성':<12}{'커머스':>6}  {'한국 질의어':<14}{'해외 질의어'}")
    for t in terms:
        print(f"  {t['ko']:<12}{t['n']:>4}개  {t['ko']:<14}{t['en']}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="구글 트렌드 수집 (지역별 질의어 분리)")
    p.add_argument("--start", default="2021-01-01")
    p.add_argument("--end", default=None, help="기본값은 오늘")
    p.add_argument("--limit", type=int, default=10, help="상위 N개 속성만")
    p.add_argument("--props", nargs="*", default=["web"],
                   choices=sorted(PROP_ALIASES), help="web / youtube")
    p.add_argument("--geos", nargs="*", default=list(GEOS))
    p.add_argument("--db", default=None)
    p.add_argument("--plan", action="store_true", help="질의 계획만 출력하고 끝낸다")
    p.add_argument("--skip", nargs="*", default=[],
                   help="건너뛸 속성. 기존 자료와 정규화 창이 달라질 때 쓴다")
    p.add_argument("--replace", action="store_true",
                   help="같은 키워드의 기존 자료를 지우고 다시 넣는다")
    args = p.parse_args(argv)

    end = args.end or utcnow_iso()[:10]
    terms = [t for t in load_terms(args.limit) if t["ko"] not in set(args.skip)]
    if not terms:
        print("해외 질의어가 있는 속성이 없다. data/attributes.yml 의 en 을 확인하라.")
        return 1

    if args.plan:
        print_plan(terms, args.geos, args.props, args.start, end)
        return 0

    conn = storage.connect(Path(args.db) if args.db else None)
    storage.init_db(conn)
    collector = GoogleTrendsCollector()
    run_id = f"gtrends-{utcnow_iso()}"
    total, failed = 0, []

    for t in terms:
        # 지역마다 다른 단어를 묻되, 저장되는 이름은 한국어 표준어 하나로 통일한다.
        by_geo = {g: [t["en"]] for g in args.geos if g != "KR"}
        by_geo["KR"] = [t["ko"]]
        for alias in args.props:
            gprop = PROP_ALIASES[alias]
            # 이어 붙이면 안 된다. 구글 트렌드는 요청 창 안에서 최댓값을 100 으로
            # 맞추므로, 창이 다른 자료를 같은 시계열에 넣으면 이음새에 없던
            # 계단이 생긴다. 다시 받을 때는 그 키워드의 기존 자료를 지운다.
            if args.replace:
                ents = [geo_entity(g, gprop) for g in args.geos]
                q = ",".join("?" for _ in ents)
                n_del = conn.execute(
                    f"DELETE FROM signal_raw WHERE channel='gtrends' "
                    f"AND keyword_raw=? AND entity IN ({q})",
                    (t["ko"], *ents)).rowcount
                conn.commit()
                if n_del:
                    print(f"  {t['ko']:<10} {alias:<8} 기존 {n_del}행 삭제")
            try:
                recs = list(collector.collect(
                    [t["ko"]], args.start, end, geos=args.geos,
                    keywords_by_geo=by_geo, candidate=t["ko"],
                    run_id=run_id, gprop=gprop))
            except GoogleTrendsUnavailable as exc:
                failed.append(f"{t['ko']}/{alias}: {exc}")
                continue
            n = storage.insert_raw(conn, recs) if recs else 0
            total += len(recs)
            print(f"  {t['ko']:<10} {alias:<8} {len(recs):>5}행 수집, {n}행 저장")

    print(f"\n합계 {total}행. 실패 {len(failed)}건")
    for f in failed:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
