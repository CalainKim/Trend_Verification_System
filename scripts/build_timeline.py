#!/usr/bin/env python3
"""달력으로 아무 구간이나 고를 수 있게 시계열을 통째로 싣는다.

    ./.venv/bin/python scripts/build_timeline.py

구간 조합이 무한해서 미리 계산해 둘 수 없다. 그래서 값을 미리 요약하지 않고
시계열 자체를 보낸다. "2023년 5월부터 8월에 뭐가 올랐나" 는 화면이 그 자리에서
평균을 내서 답한다. 계산식은 docs/design/TIMELINE_BRIEF.md 에 적었다.

축이 둘이고 갈 수 있는 깊이가 다르다. 이 사실이 화면에 보여야 한다.

    속성과 검색어   2021-12 부터. 주 단위. 소급 조회가 되는 API 라서 길다
    상품 순위       2026-09 부터. 일 단위. 크롤링이라 수집한 날부터만 있다

달력에서 상품 자료가 없는 구간을 고르면 상품 쪽은 비어야 하고, 비는 이유가
화면에 적혀야 한다. 아무 말 없이 비면 자료가 없는 것인지 그 구간에 오른
상품이 없는 것인지 구분이 안 된다.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import persistence as ps  # noqa: E402
from trend_pipeline import storage  # noqa: E402
from trend_pipeline.analytics import item_key  # noqa: E402

CHANNEL = "gtrends"
ENTITIES = ("geo=KR", "geo=US", "geo=WORLD")
GEO = {"geo=KR": "KR", "geo=US": "US", "geo=WORLD": "WORLD"}


def attr_timeline(conn) -> dict:
    """속성과 검색어의 주간 지수. 날짜는 한 번만 싣고 값은 그 순서로 맞춘다.

    키마다 날짜를 적으면 같은 날짜 253개가 수백 번 반복된다. 날짜 배열을
    따로 두고 값만 줄 세우면 파일이 3분의 1 아래로 준다.
    """
    series = ps.load_index_series(conn, CHANNEL, ENTITIES)
    weeks = ps.observed_days(series)
    out = {}
    for key, item in series.items():
        kw, entity = ps.split_series_key(key)
        out[f"{kw}@{GEO.get(entity, entity)}"] = [item.get(d) for d in weeks]
    return {"weeks": weeks, "series": out}


def item_timeline(conn, cats=None) -> dict:
    """상품 일별 순위. 목록 밖이면 null 이고 101 로 채우지 않는다.

    채우는 것은 평균을 낼 때 할 일이다. 자료에 101 을 박아 두면 화면이
    "101위였다" 로 그린다. 목록 밖은 순위를 모르는 것이지 101위가 아니다.
    """
    # 기본은 분석 범위(상의)다. 2026-11-04 부터 하의, 아우터, 신발도 모으지만
    # 여기서 같이 그리면 디자인에 건네는 사본이 조용히 달라진다. 넓히는 것은
    # 눈에 보이는 선택이어야 한다.
    codes = tuple(ps.ANALYSIS_CATEGORY_CODES if cats is None else cats)
    where, args_ = "", []
    if codes:
        marks = ", ".join("?" for _ in codes)
        where = (" AND instr(entity,'@') > 0"
                 f" AND substr(entity, instr(entity,'@') + 1) IN ({marks})")
        args_ = list(codes)
    rows = conn.execute("""
        SELECT substr(observed_at,1,10) d, entity, metric_value v,
               json_extract(metadata,'$.brand_kor') brand,
               json_extract(metadata,'$.category3') cat,
               keyword_raw name
        FROM signal_raw
        WHERE channel='commerce_rank' AND metric_type='rank'""" + where + """
        ORDER BY d
    """, args_).fetchall()
    days = sorted({r["d"] for r in rows})
    idx = {d: i for i, d in enumerate(days)}
    items: Dict[str, dict] = {}
    for r in rows:
        key = item_key(r["entity"])
        it = items.setdefault(key, {
            "name": r["name"], "brand": r["brand"], "cat": r["cat"],
            "rank": [None] * len(days)})
        it["rank"][idx[r["d"]]] = r["v"]
    return {"days": days, "items": items}


def main(argv=None) -> int:
    """속성별 흐름을 시간순으로 모은 타임라인 자료(JSON)를 만든다."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", default="build/timeline.json")
    p.add_argument("--db", default=None)
    p.add_argument("--design", default="docs/design/timeline-mock.json",
                   help="Claude Design 에 붙여넣을 줄인 사본")
    args = p.parse_args(argv)

    conn = storage.connect(Path(args.db) if args.db else None)
    conn.row_factory = sqlite3.Row

    attrs = attr_timeline(conn)
    items = item_timeline(conn)
    out = {
        "_note": "달력으로 아무 구간이나 고를 수 있게 시계열을 통째로 실었다. "
                 "구간 평균과 상승률은 화면이 그 자리에서 계산한다.",
        "coverage": {
            "attr": {"from": attrs["weeks"][0], "to": attrs["weeks"][-1],
                     "unit": "주", "n": len(attrs["weeks"]),
                     "why": "소급 조회가 되는 API 라서 과거까지 길다"},
            "item": {"from": items["days"][0], "to": items["days"][-1],
                     "unit": "일", "n": len(items["days"]),
                     "why": "크롤링이라 수집을 시작한 날부터만 있다"},
        },
        "attr": attrs,
        "item": items,
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    print(f"속성 {len(attrs['series'])}개 x 주 {len(attrs['weeks'])}개")
    print(f"상품 {len(items['items'])}개 x 일 {len(items['days'])}개")
    print(f"{path}  {path.stat().st_size / 1024:.0f}KB")

    if args.design:
        # 디자인은 자료가 몇 개냐가 아니라 어떤 모양이냐를 본다. 속성은
        # 한국만, 상품은 최근 며칠만 넣어도 화면을 그릴 수 있다.
        ko = {k: v for k, v in attrs["series"].items() if k.endswith("@KR")}
        few = dict(list(items["items"].items())[:40])
        d = Path(args.design)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(json.dumps({
            **out,
            "_note": out["_note"] + " 디자인용으로 줄인 사본이다. "
                     "속성은 한국만, 상품은 40개만 넣었다.",
            "attr": {"weeks": attrs["weeks"], "series": ko},
            "item": {"days": items["days"], "items": few},
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"디자인용 사본 {d}  {d.stat().st_size / 1024:.0f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
