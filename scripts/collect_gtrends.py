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

from trend_pipeline import snapshots, storage  # noqa: E402
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


def already_have(conn, channel: str, gprop: str) -> set:
    """이미 받은 키워드. 되풀이 수집은 한도만 쓰고 새 자료를 주지 않는다."""
    ent = "%;prop=" + gprop if gprop else "geo=%"
    rows = conn.execute(
        """
        SELECT DISTINCT keyword_raw FROM signal_raw
        WHERE channel=? AND entity LIKE ?
          AND (? <> '' OR entity NOT LIKE '%;prop=%')
        """, (channel, ent, gprop)).fetchall()
    return {r[0] for r in rows}


def fresh_terms(conn, channel: str, gprop: str, days: int, today: str) -> set:
    """마지막 관측이 today 기준 days 일 안에 있는 키워드. 이것들은 다시 받지 않는다.

    처음 채우기(--missing-only)만 있으면 한 번 받은 속성은 영영 다시 받지 않아서
    시계열이 그날에서 멈춘다. 2026-10-25 에서 멈춘 채 2주를 보냈고, 화면은 최신 주의
    기준일까지 검색 자료가 없다는 이유로 모든 상품을 "검색 교차에서 걸러짐" 으로
    떨어뜨렸다. 새 주가 생길 만큼 오래된 것만 골라 다시 받는다.

    한국 시계열만 본다. 해외는 같은 요청에서 함께 받으므로 날짜가 같이 움직인다.
    """
    from datetime import date, timedelta
    cutoff = (date.fromisoformat(today[:10]) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """
        SELECT keyword_raw FROM signal_raw
        WHERE channel=? AND entity=?
        GROUP BY keyword_raw HAVING MAX(substr(observed_at, 1, 10)) >= ?
        """, (channel, geo_entity("KR", gprop), cutoff)).fetchall()
    return {r[0] for r in rows}


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
    """몇 번 요청할지, 얼마나 걸릴지, 속성마다 어떤 검색어를 쓸지 미리 보여 준다."""
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
    """명령줄 인자를 읽어 구글 트렌드를 받는다. 빠진 것만, 오래된 것만 골라 받을 수도 있다."""
    p = argparse.ArgumentParser(description="구글 트렌드 수집 (지역별 질의어 분리)")
    p.add_argument("--start", default="2021-01-01")
    p.add_argument("--end", default=None, help="기본값은 오늘")
    p.add_argument("--limit", type=int, default=10, help="상위 N개 속성만")
    p.add_argument("--props", nargs="*", default=["web"],
                   choices=sorted(PROP_ALIASES), help="web / youtube")
    p.add_argument("--geos", nargs="*", default=list(GEOS))
    p.add_argument("--db", default=None)
    p.add_argument("--plan", action="store_true", help="질의 계획만 출력하고 끝낸다")
    p.add_argument("--missing-only", action="store_true",
                   help="이미 받은 속성은 건너뛴다. 되풀이 수집은 한도만 쓴다")
    p.add_argument("--max-new", type=int, default=None,
                   help="이번 실행에서 새로 받을 속성 수 상한. --limit 과 달리 "
                        "이미 받은 것을 뺀 뒤에 센다")
    p.add_argument("--max-attempts", type=int, default=None,
                   help="한 요청의 재시도 횟수. 1 이면 막혔을 때 바로 포기한다")
    p.add_argument("--stop-on-block", action="store_true",
                   help="429 를 만나면 남은 속성을 건너뛰고 끝낸다")
    p.add_argument("--skip", nargs="*", default=[],
                   help="건너뛸 속성. 기존 자료와 정규화 창이 달라질 때 쓴다")
    p.add_argument("--replace", action="store_true",
                   help="같은 키워드의 기존 자료를 지우고 다시 넣는다. 받는 데 "
                        "성공한 뒤에만 지운다")
    p.add_argument("--stale-days", type=int, default=None,
                   help="마지막 관측이 이 일수보다 오래된 속성만 다시 받는다. "
                        "새 주를 덧붙이는 갱신용이며 --replace 와 함께 쓴다")
    p.add_argument("--snapshot-dir", default=str(ROOT / "data" / "snapshots"),
                   help="CSV 스냅샷 경로 (빈 문자열이면 기록 안 함). DB 는 "
                        "저장소에서 제외되므로 여기 남은 것만 다른 컴퓨터로 넘어간다")
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
    collector = (GoogleTrendsCollector(max_attempts=args.max_attempts)
                 if args.max_attempts else GoogleTrendsCollector())
    run_id = f"gtrends-{utcnow_iso()}"
    total, failed = 0, []

    if args.stale_days is not None and not args.replace:
        # 눈금이 다른 창을 같은 시계열에 덧붙이면 이음새에 없던 계단이 생긴다
        print("--stale-days 는 --replace 와 함께 써야 한다. 이어 붙이면 눈금이 섞인다")
        return 2

    def skip_set(alias):
        """이번에 건너뛸 속성 목록을 정한다. 이미 새 자료가 있는 속성이다."""
        gprop = PROP_ALIASES[alias]
        if args.stale_days is not None:
            return fresh_terms(conn, "gtrends", gprop, args.stale_days, end)
        return already_have(conn, "gtrends", gprop) if args.missing_only else set()

    have = {alias: skip_set(alias) for alias in args.props}
    blocked = False
    started = 0          # 이번 실행에서 실제로 손댄 속성 수

    for t in terms:
        if blocked:
            break
        todo = [a for a in args.props if t["ko"] not in have[a]]
        if not todo:
            continue
        if args.max_new is not None and started >= args.max_new:
            print(f"\n이번 실행 상한 {args.max_new}개에 도달했다. "
                  f"다음 실행에서 이어 받는다.")
            break
        started += 1
        # 지역마다 다른 단어를 묻되, 저장되는 이름은 한국어 표준어 하나로 통일한다.
        by_geo = {g: [t["en"]] for g in args.geos if g != "KR"}
        by_geo["KR"] = [t["ko"]]
        for alias in args.props:
            gprop = PROP_ALIASES[alias]
            if t["ko"] in have[alias]:
                continue
            try:
                recs = list(collector.collect(
                    [t["ko"]], args.start, end, geos=args.geos,
                    keywords_by_geo=by_geo, candidate=t["ko"],
                    run_id=run_id, gprop=gprop))
            except GoogleTrendsUnavailable as exc:
                failed.append(f"{t['ko']}/{alias}: {exc}")
                if args.stop_on_block and "429" in str(exc):
                    # 한도에 걸렸으면 남은 속성도 막힌다. 계속 두드리면
                    # 풀리는 시점만 늦춘다.
                    blocked = True
                    break
                continue
            # 이어 붙이면 안 된다. 구글 트렌드는 요청 창 안에서 최댓값을 100 으로
            # 맞추므로, 창이 다른 자료를 같은 시계열에 넣으면 이음새에 없던
            # 계단이 생긴다. 다시 받을 때는 그 키워드의 기존 자료를 지운다.
            #
            # 지우는 것은 받는 데 성공한 뒤다. 먼저 지우면 한도(429)에 걸린 순간
            # 그 키워드 자료가 DB 에서 사라진다. 시간별 수집은 한도에 자주 걸린다.
            old_keys = set()
            if args.replace and recs:
                ents = [geo_entity(g, gprop) for g in args.geos]
                q = ",".join("?" for _ in ents)
                # 옛 행이 있던 해도 기억해 둔다. 새 자료가 그 해에 닿지 않으면
                # 그 해 CSV 가 다시 쓰이지 않아 지운 옛 눈금 행이 파일에 남고,
                # 다른 컴퓨터에서 CSV 로 DB 를 다시 만들 때 되살아난다.
                old_keys = {r[0] for r in conn.execute(
                    f"SELECT DISTINCT observed_at FROM signal_raw WHERE channel='gtrends' "
                    f"AND keyword_raw=? AND entity IN ({q})", (t["ko"], *ents))}
                n_del = conn.execute(
                    f"DELETE FROM signal_raw WHERE channel='gtrends' "
                    f"AND keyword_raw=? AND entity IN ({q})",
                    (t["ko"], *ents)).rowcount
                # 여기서 확정하지 않는다. 아래 insert_raw 가 끝에서 확정하므로
                # 지우기와 넣기가 한 번에 들어간다. 그 사이에 멈춰도 자료가 비지 않는다.
                if n_del:
                    print(f"  {t['ko']:<10} {alias:<8} 기존 {n_del}행 삭제")
            n = storage.insert_raw(conn, recs) if recs else 0
            if recs and args.snapshot_dir:
                # DB 가 아니라 이 CSV 가 원본이다. 한 속성을 받을 때마다 써야
                # 중간에 한도에 걸려 끝나도 받은 만큼은 텍스트로 남는다.
                snapshots.write_snapshots_for(conn, Path(args.snapshot_dir), recs)
                done_years = {snapshots.partition_key("gtrends", r.observed_date) for r in recs}
                for key in sorted({snapshots.partition_key("gtrends", o) for o in old_keys} - done_years):
                    snapshots.write_snapshot(conn, Path(args.snapshot_dir), "gtrends", key)
            total += len(recs)
            print(f"  {t['ko']:<10} {alias:<8} {len(recs):>5}행 수집, {n}행 저장")

    if blocked:
        print("\n한도에 걸려 남은 속성을 건너뛴다. 다음 실행에서 이어 받는다.")
    print(f"\n합계 {total}행. 실패 {len(failed)}건")
    for f in failed:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
