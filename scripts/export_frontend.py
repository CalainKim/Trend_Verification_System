#!/usr/bin/env python3
"""Trend Monitor 화면이 읽는 데이터를 파이프라인에서 만든다.

화면(Claude Design 의 Trend Monitor v8)은 세 상수를 쓴다. 이 스크립트는 같은
모양을 실제 수집분으로 채워 준다. 화면 구조는 건드리지 않는다.

    CASES   판정할 문제지      [{case_id, candidate, claim, evidence, features, ...}]
    TRACK   유형 다주 궤적     {weeks, tops, rises, brands, score, parts, ...}
    SCORE   판정 성적표        {accuracy, coverage, precision, recall, ...}
    G       속성별 검색 추이   {d0, last, k4, kp, kr[26], us[26], lead}
    P       속성별 상품 목록   [순위, 지난주순위, 브랜드, 상품명, 판매가, 성별,
                              할인율, 지난주할인율, 사진주소]
    LEDGER  검증 기록         [상품명, 기준순위, 감지순위, 확인순위, 남음여부]

화면의 필터 5단계 가운데 할인 효과와 해외 선행이 "연결 예정"으로 비어 있었다.
둘 다 수집된 자료로 채울 수 있어서 P 의 일곱 번째 값(할인율)과 G 의 lead 를
추가했다. 기존 여섯 자리와 G 의 기존 키는 그대로라 화면이 안 고쳐져도 깨지지
않는다.

    ./scripts/export_frontend.py                 최신 주 기준
    ./scripts/export_frontend.py --week 2026-11-01
    ./scripts/export_frontend.py --json          JSON 으로도 저장

k4 는 마지막 4주 평균, kp 는 그 직전 4주 평균이다. 화면의 "최근 4주" 비교가
이 두 값을 쓴다.

남음 판정은 (기준순위 - 확인순위) / (기준순위 - 감지순위) >= KEEP_RATIO 다.
persistence.py 와 같은 식이므로 두 값을 따로 관리하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import extract_attributes as ea  # noqa: E402
from trend_pipeline import features as ft  # noqa: E402
from trend_pipeline import storage  # noqa: E402
from trend_pipeline.persistence import KEEP_RATIO, MIN_RISE  # noqa: E402

WEEKS = 26          # 화면이 그리는 주 수
AVG_WEEKS = 4       # k4, kp 의 구간 길이
TOP = 100           # 화면이 보는 순위 범위
RANK_CATEGORIES = ("남성의류>상의", "여성의류>상의")
GENDER = {"남성의류": "남", "여성의류": "여"}

# 화면의 유형 분류 규칙. Trend Monitor v8 의 TYPE_RULES 를 그대로 옮겼다.
# 순서가 의미를 가진다. 먼저 맞는 규칙이 이긴다. 후드이면서 니트인 상품은
# 후드로 간다. 화면과 같은 결과를 내려면 순서를 바꾸면 안 된다.
TYPE_RULES = [
    ("후드", r"hood|후드|후디"),
    ("맨투맨", r"sweat|스웨트|스웻|맨투맨"),
    ("티셔츠", r"t-?shirt|\btee\b|티셔츠"),
    ("니트", r"knit|니트|폴라"),
    ("블라우스", r"blouse|블라우스"),
    ("롱슬리브", r"long ?sleeve|롱 ?슬리브|긴팔|henley"),
    ("이너웨어", r"underwear|balaclava"),
    ("탑", r"top|탑"),
]
_TYPE_RE = [(name, re.compile(pat, re.I)) for name, pat in TYPE_RULES]


def type_of(name: str) -> str:
    for label, rx in _TYPE_RE:
        if rx.search(name):
            return label
    return "기타"


def snapshot_days(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT substr(observed_at, 1, 10) FROM signal_raw"
        " WHERE channel = 'commerce_rank' AND metric_type = 'rank' ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows]


def pick_weeks(days: List[str], week: Optional[str], span: int = 7) -> List[str]:
    """확인, 감지, 기준 순위를 읽을 세 날짜를 고른다.

    7일 간격이 정확히 맞는 날이 없으면 가장 가까운 수집일로 당긴다. 29CM 수집이
    하루 빠진 날이 있어 고정 간격을 쓰면 빈 날을 집는다.
    """
    from datetime import date, timedelta

    anchor = week or days[-1]
    if anchor not in days:
        raise SystemExit(f"{anchor} 에 29CM 수집이 없다. 있는 날: {days[-5:]}")
    out = [anchor]
    cur = date.fromisoformat(anchor)
    for _ in range(2):
        target = cur - timedelta(days=span)
        earlier = [d for d in days if d < out[-1]]
        if not earlier:
            raise SystemExit(f"{out[-1]} 이전 수집일이 없다. 주간 비교를 할 수 없다")
        nearest = min(earlier, key=lambda d: abs((date.fromisoformat(d) - target).days))
        out.append(nearest)
        cur = date.fromisoformat(nearest)
    return out[::-1]   # 기준, 감지, 확인


def ranks_on(conn: sqlite3.Connection, day: str) -> Dict[str, dict]:
    """그날 마지막 수집 시점의 TOP100.

    수집이 하루 두 번(10시, 22시) 돌기 때문에 그날 전체를 모으면 두 시점의
    합집합이 되어 상품이 200개를 넘는다. 순위는 한 시점에서만 뜻이 있으므로
    가장 늦은 시각 하나만 쓴다.
    """
    last_at = conn.execute(
        "SELECT MAX(observed_at) FROM signal_raw"
        " WHERE channel = 'commerce_rank' AND metric_type = 'rank'"
        "   AND substr(observed_at, 1, 10) = ?",
        (day,),
    ).fetchone()[0]
    rows = conn.execute(
        """
        SELECT observed_at, keyword_raw, entity, metric_value, metadata
        FROM signal_raw
        WHERE channel = 'commerce_rank' AND metric_type = 'rank'
          AND observed_at = ?
        ORDER BY metric_value
        """,
        (last_at,),
    ).fetchall()
    out: Dict[str, dict] = {}
    for _, name, entity, rank, meta in rows:
        m = json.loads(meta)
        if m.get("ranking_category_name") not in RANK_CATEGORIES:
            continue
        if rank > TOP:
            continue
        out[entity] = {
            "name": name,
            "rank": int(rank),
            "brand": m.get("brand_kor") or m.get("brand_eng") or "",
            "price": int(m.get("sale_price") or 0),
            "gender": GENDER.get(m.get("category1"), ""),
            "is_new": bool(m.get("is_new")),
            "sale_percent": m.get("sale_percent"),
            "image_url": m.get("image_url"),
        }
    return out


def weekly_series(conn: sqlite3.Connection, keyword: str, entity: str,
                  weeks: int) -> List[dict]:
    rows = conn.execute(
        """
        SELECT observed_at, metric_value FROM signal_raw
        WHERE channel = 'gtrends' AND metric_type = 'search_index'
          AND keyword_raw = ? AND entity = ?
        ORDER BY observed_at DESC LIMIT ?
        """,
        (keyword, entity, weeks),
    ).fetchall()
    return [{"at": r[0][:10], "v": r[1]} for r in rows][::-1]


def lead_of(conn: sqlite3.Connection, keyword: str, as_of: str,
            geo: str = "US", window: int = 1500) -> Optional[dict]:
    """해외가 한국보다 며칠 앞섰는지. 문턱을 못 넘으면 None 이다.

    lead_days 는 양수면 해외 선행, 음수면 한국 선행이다. 상관이 문턱
    (features.MIN_LEAD_CORRELATION) 에 못 미치거나 최적값이 탐색 범위 끝에
    걸리면 쓰지 않는다. 끝에 걸렸다는 건 진짜 최적이 범위 밖일 수 있다는 뜻이다.
    """
    try:
        r = ft.lead_lag(conn, keyword, as_of, geo, window_days=window)
    except ft.MixedQueryWindow:
        return None
    if r is None or not r.reliable or r.at_boundary:
        return None
    return {"geo": r.geo, "days": r.lead_days, "corr": round(r.correlation, 2),
            "n": r.n_overlap}


def build_g(conn: sqlite3.Connection, keywords: List[str],
            as_of: Optional[str] = None) -> Dict[str, dict]:
    g: Dict[str, dict] = {}
    for kw in keywords:
        kr = weekly_series(conn, kw, "geo=KR", WEEKS)
        us = weekly_series(conn, kw, "geo=US", WEEKS)
        if len(kr) < AVG_WEEKS * 2 or len(us) < AVG_WEEKS:
            continue
        vals = [p["v"] for p in kr]
        last4 = vals[-AVG_WEEKS:]
        prev4 = vals[-AVG_WEEKS * 2:-AVG_WEEKS]
        g[kw] = {
            "d0": kr[0]["at"],
            "last": kr[-1]["at"],
            "k4": round(sum(last4) / len(last4), 1),
            "kp": round(sum(prev4) / len(prev4), 1),
            "kr": [round(v) for v in vals],
            "us": [round(p["v"]) for p in us],
        }
        if as_of:
            lead = lead_of(conn, kw, as_of)
            if lead:
                g[kw]["lead"] = lead
    return g


# 유형 이름과 같은 뜻인 속성이 있다. 티셔츠 유형 아래 세부 속성으로 "티셔츠"가
# 다시 나오면 아무것도 설명하지 못한다. 다만 P 에서 빼면 안 된다. 화면이 P 의
# 합집합으로 상품 목록을 만들기 때문에, 다른 속성이 하나도 없는 상품이 통째로
# 사라진다. 화면에는 유형별로 거르는 TYPE_SKIP 자리가 따로 있으므로 그 표를
# 사전에서 만들어 함께 내보낸다.


def self_attribute(canonical: str) -> bool:
    """이 속성이 어떤 유형의 이름 그 자체인가.

    사전 74종 가운데 7개가 여기 걸린다. 긴팔(롱슬리브), 니트, 티셔츠,
    후드티(후드), 맨투맨, 블라우스, 탑이다. 전부 진짜 자기참조라서 그룹으로
    한 번 더 거르지 않아도 된다.
    """
    return type_of(canonical) != "기타"


def build_type_skip(attrs) -> Dict[str, List[str]]:
    """유형마다 숨길 세부 속성. 화면의 TYPE_SKIP 을 대신한다."""
    skip: Dict[str, List[str]] = {label: [] for label, _ in TYPE_RULES}
    for a in attrs:
        canon = a["canonical"]
        if not self_attribute(canon):
            continue
        skip[type_of(canon)].append(canon)
    for label in skip:
        skip[label].sort()
    return skip


def build_p(this_week: Dict[str, dict], last_week: Dict[str, dict],
            attrs, colors) -> Dict[str, list]:
    """속성별 상품 목록. 지난주 TOP100 에 없었으면 지난주 순위는 null 이다."""
    p: Dict[str, list] = defaultdict(list)
    for entity, cur in this_week.items():
        prev = last_week.get(entity)
        row = [
            cur["rank"],
            prev["rank"] if prev else None,
            cur["brand"],
            cur["name"],
            cur["price"],
            cur["gender"],
            cur["sale_percent"],
            # 할인 때문에 올랐는지 보려면 지난주와 견줘야 한다. 이번 주 값만으로는
            # 원래 상시 할인하던 상품과 이번에 할인을 건 상품을 구분하지 못한다.
            prev["sale_percent"] if prev else None,
            # 원본은 280KB 라 그대로 쓰면 화면이 무겁다. CDN 이 ?width 로 줄여
            # 주므로 상세 화면에 맞는 크기만 받는다.
            cur["image_url"] + "?width=240&format=webp" if cur["image_url"] else None,
        ]
        for a in ea.extract(cur["name"], attrs, colors):
            p[a["canonical"]].append(row)
    for k in p:
        p[k].sort(key=lambda r: r[0])
    return dict(p)


def build_ledger(base: Dict[str, dict], detect: Dict[str, dict],
                 hold: Dict[str, dict]) -> List[list]:
    """기준에서 감지 사이에 오른 상품이 확인 시점에 남아 있는지.

    남음 판정은 persistence.py 와 같은 식을 쓴다. 상승분의 절반 넘게 남으면
    남음이다. 확인 시점에 TOP100 밖으로 나갔으면 순위를 null 로 둔다.
    """
    out: List[list] = []
    for entity, d in detect.items():
        b = base.get(entity)
        gain = (b["rank"] - d["rank"]) if b else None
        if gain is None or gain < MIN_RISE:
            continue
        h = hold.get(entity)
        if h is None:
            out.append([d["name"], b["rank"], d["rank"], None, False])
            continue
        kept = (b["rank"] - h["rank"]) / gain >= KEEP_RATIO
        out.append([d["name"], b["rank"], d["rank"], h["rank"], kept])
    out.sort(key=lambda r: (not r[4], r[2]))
    return out


# 판정기가 읽는 키만 내보낸다. 정답(labels.sealed.json)은 절대 넣지 않는다.
# 넣으면 파일을 받은 사람이 문제지를 보고 답을 맞출 수 있어 채점이 뜻을 잃는다.
CASE_KEYS = ("case_id", "candidate", "claim", "simulated_cutoff", "evidence",
             "features", "limitations", "historical_available_at",
             "experiment_type")


def _walk_values(obj):
    """중첩된 자료에서 잎 값만 꺼낸다. 정답 누출 검사에 쓴다."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_values(v)
    else:
        yield obj


def build_cases(benchmark: Path) -> list:
    """검증 파트가 파일 하나로 판정할 수 있게 문제지를 싣는다.

    화면의 급상승 목록은 이번 주 상품이고 벤치마크는 다른 주의 케이스다. 둘은
    겹치지 않으므로, 판정을 받으려면 케이스를 따로 실어야 한다.
    """
    out = []
    for f in sorted((benchmark / "cases").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out.append({k: d[k] for k in CASE_KEYS if k in d})
    return out


def build_track(conn: sqlite3.Connection, weeks: int = 6) -> Optional[dict]:
    """유형 다주 궤적과 점수. 화면이 "계속 지켜본다" 에 답하는 자리다.

    점수는 예측이 아니라 관측 요약이다. 유형 단위로 검증하려면 라벨이 필요한데
    28건에 기저율 89.3% 라 어떤 점수도 찍기보다 낫다고 증명할 수 없다. 그래서
    화면에 계산식과 함께 "예측 아님" 을 적어야 한다.
    """
    import track_types as tt

    days = snapshot_days(conn)
    chain = tt.weekly_chain(days, weeks)
    if len(chain) < 3:
        print(f"  주간 비교에 쓸 수집일이 {len(chain)}개뿐이라 궤적을 못 낸다")
        return None
    pairs = [(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    snaps = [(d, tt.week_snapshot(conn, pd, d)) for pd, d in pairs]
    types = {t for _, s in snaps for t in s}
    out = {}
    for t in types:
        got = [s.get(t, {}) for _, s in snaps]
        rec = {
            "weeks": [d for d, _ in snaps],
            "verdicts": [g.get("verdict", tt.NONE) for g in got],
            "tops": [g.get("n_top", 0) for g in got],
            "rises": [g.get("n_rise", 0) for g in got],
            "brands": [g.get("n_brand", 0) for g in got],
            # 판정은 브랜드 개수가 아니라 1위 쏠림을 본다. 화면이 근거를
            # 보여 주려면 이 값이 있어야 한다.
            "top_brand": got[-1].get("top_brand"),
            "top_brand_n": got[-1].get("top_brand_n", 0),
            "top_brand_share": got[-1].get("top_brand_share", 0.0),
        }
        streak = best = 0
        for v in rec["verdicts"]:
            streak = streak + 1 if v == tt.CAND else 0
            best = max(best, streak)
        dirn, change = tt.direction(rec["tops"])
        rec.update(streak=best, direction=dirn, change=round(change, 3))
        rec.update(tt.type_score(rec))
        out[t] = rec
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["score"]))


def build_score(benchmark: Path, verdicts: Optional[Path]) -> Optional[dict]:
    """판정 성적표. 화면의 검증 기록 타일 네 개가 읽는다.

    정답 파일을 읽지만 내보내는 것은 합계뿐이다. 케이스별 정답은 나가지 않는다.
    나가면 화면을 받은 사람이 문제지를 보고 답을 맞출 수 있게 된다.

    정확도와 두 비율은 서로 다른 것을 잰다.
      정확도   답한 전체 가운데 맞힌 비율
      정밀도   지속이라 말한 것 가운데 실제로 지속한 비율
      재현율   실제로 지속한 것 가운데 미리 짚은 비율
    """
    if verdicts is None:
        return None
    sys.path.insert(0, str(ROOT / "scripts"))
    import score_verdicts as sv
    import trend_pipeline.scoring as sc

    try:
        labels = sv.load_labels(benchmark)
        got = sv.load_verdicts(verdicts)
    except SystemExit as exc:
        print(f"  성적표를 낼 수 없다: {exc}")
        return None
    card = sc.score(labels, got)
    if card.accuracy is None:
        print("  답한 케이스가 없어 성적표가 비어 있다")
        return None
    c = card.confusion
    tp = c.get("persist->persist", 0)
    fp = c.get("fade->persist", 0)
    fn = c.get("persist->fade", 0)
    return {
        "n_cases": card.n_cases,
        "n_answered": card.n_answered,
        "coverage": round(card.coverage, 3),
        "accuracy": round(card.accuracy, 3),
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "base_rate": round(card.base_rate_all, 3) if card.base_rate_all else None,
        "base_rate_answered": (round(card.base_rate_answered, 3)
                               if card.base_rate_answered else None),
        "ci": [round(card.ci[0], 3), round(card.ci[1], 3)],
        "beats_base_rate": card.beats_base_rate,
        # 화면이 숫자만 보여 주면 표본이 몇인지 안 보인다. 단서를 같이 낸다.
        "note": (f"답한 {card.n_answered}건 기준"
                 + ("" if card.beats_base_rate else ", 찍기보다 낫다고 하기엔 표본 부족")),
    }


def js_literal(name: str, value) -> str:
    return f"const {name} = {json.dumps(value, ensure_ascii=False)};\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--week", default=None, help="확인 시점 날짜 (기본: 최신 수집일)")
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--benchmark-dir", type=Path, default=ROOT / "benchmark",
                    help="성적표를 낼 때 쓸 벤치마크 경로")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "frontend_data.js")
    ap.add_argument("--json", action="store_true", help="JSON 으로도 저장")
    ap.add_argument("--verdicts", type=Path, default=None,
                    help="판정 파일. 주면 성적표를 함께 낸다")
    ap.add_argument("--no-lead", action="store_true",
                    help="해외 선행 계산을 건너뛴다. 속성마다 5년치를 훑어서 느리다")
    args = ap.parse_args(argv)

    conn = storage.connect(args.db)
    days = snapshot_days(conn)
    if len(days) < 3:
        print(f"29CM 수집일이 {len(days)}일뿐이라 3주 비교를 할 수 없다")
        return 1
    base_d, detect_d, hold_d = pick_weeks(days, args.week)
    print(f"기준 {base_d}  감지 {detect_d}  확인 {hold_d}")

    base, detect, hold = (ranks_on(conn, d) for d in (base_d, detect_d, hold_d))
    print(f"TOP100 상품  기준 {len(base)}개, 감지 {len(detect)}개, 확인 {len(hold)}개")
    for label, n in (("기준", len(base)), ("감지", len(detect)), ("확인", len(hold))):
        if n != TOP * len(RANK_CATEGORIES):
            print(f"  주의. {label} 시점 상품이 {n}개다. "
                  f"{TOP * len(RANK_CATEGORIES)}개여야 한다")

    attrs, _stop, colors = ea.load_dictionary()
    p = build_p(hold, detect, attrs, colors)
    type_skip = build_type_skip(attrs)
    ledger = build_ledger(base, detect, hold)

    # 검색 추이는 이번 주 상품에 실제로 붙은 속성만 내보낸다. 화면이 세부 속성을
    # 누를 때만 쓰므로 안 쓰는 키워드를 넣으면 파일만 커진다.
    g = build_g(conn, sorted(p), as_of=None if args.no_lead else hold_d)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    head = (
        f"// scripts/export_frontend.py 가 만든 파일이다. 직접 고치지 않는다.\n"
        f"// 기준 {base_d}, 감지 {detect_d}, 확인 {hold_d}\n"
    )
    # 화면은 "10/25에서 11/01" 같은 날짜를 다섯 군데에 글자로 박아 두었다. 주가
    # 바뀌면 그 글자도 같이 바뀌어야 하므로 날짜를 상수로 함께 내보낸다.
    # base/detect/hold 는 화면에 찍는 "10/18" 꼴, 뒤의 ISO 는 날짜 비교용이다.
    # 검색 자료가 충분히 최신인지 보는 G[a].last >= ... 비교가 baseISO 를 쓴다.
    week = {
        "base": base_d[5:].replace("-", "/"),
        "detect": detect_d[5:].replace("-", "/"),
        "hold": hold_d[5:].replace("-", "/"),
        "baseISO": base_d,
        "detectISO": detect_d,
        "holdISO": hold_d,
        # 다음 채점일. 화면이 LLM 에게 "오늘과 다음 채점일" 을 알려 줄 때 쓴다.
        "nextISO": (date.fromisoformat(hold_d) + timedelta(days=7)).isoformat(),
    }
    track = build_track(conn) or {}
    cases = build_cases(args.benchmark_dir)
    score = build_score(args.benchmark_dir, args.verdicts)
    args.out.write_text(
        head + js_literal("G", g) + js_literal("P", p) + js_literal("LEDGER", ledger)
        + js_literal("TYPE_SKIP", type_skip) + js_literal("WEEK", week)
        + js_literal("TRACK", track) + js_literal("SCORE", score)
        + js_literal("CASES", cases),
        encoding="utf-8",
    )
    if args.json:
        args.out.with_suffix(".json").write_text(
            json.dumps({"weeks": [base_d, detect_d, hold_d], "G": g, "P": p,
                        "LEDGER": ledger, "TYPE_SKIP": type_skip, "WEEK": week,
                        "TRACK": track, "SCORE": score, "CASES": cases},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    kept = sum(1 for r in ledger if r[4])
    print()
    leads = {k: v["lead"] for k, v in g.items() if "lead" in v}
    home = sum(1 for v in leads.values() if v["days"] < 0)
    print(f"G       검색 추이 {len(g)}개 속성, 해외 선행 판정 {len(leads)}건 "
          f"(한국 선행 {home}건, 해외 선행 {len(leads) - home}건)")
    names = {r[3] for rows in p.values() for r in rows}
    disc = {r[3] for rows in p.values() for r in rows if (r[6] or 0) > 0}
    # 지난주보다 할인을 더 건 상품. 화면의 할인 효과 단계가 볼 값이다.
    deeper = {r[3] for rows in p.values() for r in rows
              if r[7] is not None and (r[6] or 0) - r[7] >= 5}
    print(f"P       상품 목록 {len(p)}개 속성, 상품 {len(names)}개, 연인원 "
          f"{sum(len(v) for v in p.values())}건")
    if len(names) != len(hold):
        print(f"  주의. 확인 시점 TOP100 {len(hold)}개 중 {len(hold) - len(names)}개는 "
              f"사전에 걸리는 속성이 없어 화면에 안 나온다")
    print(f"        할인 중인 상품 {len(disc)}개 / {len(names)}개, "
          f"지난주보다 5%p 이상 더 할인 {len(deeper)}개")
    withimg = {r[3] for rows in p.values() for r in rows if r[8]}
    print(f"        사진이 있는 상품 {len(withimg)}개 / {len(names)}개")
    print("TYPE_SKIP  " + ", ".join(f"{k}:{v}" for k, v in type_skip.items() if v))
    # 정답 누출 검사. 문자열에 'persist' 가 있는지로 보면 experiment_type 의
    # "persistence-v1" 에 걸린다. 실제로 막아야 하는 것은 정답 파일에 적힌 값이
    # 케이스 안에 값으로 들어가는 경우다. 정답 파일을 읽어 그 값과 대조한다.
    sealed = args.benchmark_dir / "labels.sealed.json"
    if sealed.exists():
        answers = json.loads(sealed.read_text(encoding="utf-8"))["labels"]
        leaked = []
        for c in cases:
            want = answers.get(c["case_id"])
            if want is None:
                continue
            flat = [v for v in _walk_values(c)]
            if want in flat:
                leaked.append(c["case_id"])
        if leaked:
            raise SystemExit(f"케이스에 정답이 값으로 들어 있다: {leaked[:3]}")
        print(f"  정답 누출 검사 통과 ({len(answers)}건 대조)")
    print(f"CASES   문제지 {len(cases)}건 ({len(json.dumps(cases, ensure_ascii=False).encode()) // 1024}KB), 정답은 넣지 않았다")
    if track:
        top = list(track.items())[:3]
        print(f"TRACK   유형 {len(track)}개 {len(next(iter(track.values()))['weeks'])}주, "
              + ", ".join(f"{k} {v['score']}점" for k, v in top))
    if ledger:
        print(f"LEDGER  {len(ledger)}건 중 {kept}건 남음 ({kept / len(ledger) * 100:.1f}%)")
    else:
        print("LEDGER  해당 주에 10계단 이상 오른 상품이 없다")
    print(f"\n{args.out} 에 저장했다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
