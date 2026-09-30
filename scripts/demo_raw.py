#!/usr/bin/env python3
"""원본 → 정제 과정을 날 것 그대로 보여준다.

    python scripts/demo_raw.py              # 전체
    python scripts/demo_raw.py --rows 40    # 각 구간에서 보여줄 줄 수
    python scripts/demo_raw.py --only 2
    python scripts/demo_raw.py --live       # API 를 실제로 호출해 원문을 보여줌

해설은 최소로 두고 실제 값을 많이 띄운다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import clustering, embeddings, features as ft, storage, vectorstore  # noqa: E402

D, R, Y, G, C, B = "\033[2m", "\033[0m", "\033[33m", "\033[32m", "\033[36m", "\033[1m"
TTY = sys.stdout.isatty()


def dim(s):   return f"{D}{s}{R}" if TTY else s
def hi(s):    return f"{Y}{s}{R}" if TTY else s
def ok(s):    return f"{G}{s}{R}" if TTY else s
def cy(s):    return f"{C}{s}{R}" if TTY else s
def bold(s):  return f"{B}{s}{R}" if TTY else s


def rule(n, title):
    print()
    print(dim("─" * 96))
    print(bold(f"[{n}] {title}"))
    print(dim("─" * 96))


def cmd(line):
    print(cy(f"$ {line}"))


# ───────────────────────────────────────────────────────── 1. API 원문

def s1(conn, rows, live):
    rule(1, "네이버 API 원문 응답")
    if live:
        cmd("curl -X POST naverapihub.apigw.ntruss.com/search-trend/v1/search")
        from trend_pipeline import config
        import requests
        cid, sec = config.naver_credentials()
        body = {"startDate": "2026-09-01", "endDate": "2026-09-10", "timeUnit": "date",
                "keywordGroups": [{"groupName": "맨투맨", "keywords": ["맨투맨"]}]}
        r = requests.post("https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
                          data=json.dumps(body, ensure_ascii=False).encode(),
                          headers={"X-NCP-APIGW-API-KEY-ID": cid,
                                   "X-NCP-APIGW-API-KEY": sec,
                                   "Content-Type": "application/json"}, timeout=25)
        print(dim(json.dumps(r.json(), ensure_ascii=False, indent=2)[:1400]))
    else:
        print(dim(json.dumps({
            "startDate": "2026-09-01", "endDate": "2026-09-10", "timeUnit": "date",
            "results": [{"title": "맨투맨", "keywords": ["맨투맨"], "data": [
                {"period": "2026-09-01", "ratio": 41.17647},
                {"period": "2026-09-02", "ratio": 38.23529},
                {"period": "2026-09-03", "ratio": 52.94117}]}]},
            ensure_ascii=False, indent=2)))
        print(dim("  (--live 를 붙이면 실제 호출)"))

    print()
    print(hi("  ratio 는 절대 검색량이 아니라 이 응답 안에서 최댓값=100 으로"))
    print(hi("  정규화된 값이다. 다른 요청의 값과 직접 비교할 수 없다."))


# ───────────────────────────────────────────────── 2. 29CM 원본 상품명

def s2(conn, rows, live):
    rule(2, f"29CM 수집 원본 상품명 (앞 {rows}건)")
    cmd("SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank'")
    names = [r[0] for r in conn.execute(
        "SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank' "
        "ORDER BY keyword_raw LIMIT ?", (rows,))]
    for n in names:
        print(dim(f"  {n}"))
    total = conn.execute("SELECT COUNT(DISTINCT keyword_raw) FROM signal_raw "
                         "WHERE channel='commerce_rank'").fetchone()[0]
    print(dim(f"  ... 총 {total}건"))
    print()
    print(hi("  프로모션 태그, 배송 차수, 품번, 색상이 상품명에 섞여 있다."))


# ───────────────────────────────────────────────────────── 3. 정규화

def s3(conn, rows, live):
    rule(3, f"정규화 — 임베딩에 넣기 전 군더더기 제거 (앞 {rows}건)")
    cmd("embeddings.normalize_for_embedding(name)")
    names = [r[0] for r in conn.execute(
        "SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank' "
        "AND (keyword_raw LIKE '%[%' OR keyword_raw LIKE '%(%' OR keyword_raw LIKE '%차%') "
        "ORDER BY keyword_raw LIMIT ?", (rows,))]
    changed = 0
    for n in names:
        cleaned = embeddings.normalize_for_embedding(n)
        if cleaned != n:
            changed += 1
            print(f"  {dim(n[:62])}")
            print(f"      → {ok(cleaned[:62])}")
    print()
    print(hi(f"  {changed}건 변경. 이걸 안 하면 '[29CM 단독]' 같은 공통 접두사만으로"))
    print(hi("  서로 다른 품목이 한 덩어리로 묶인다."))


# ───────────────────────────────────────────── 4. 클러스터링 결과

def s4(conn, rows, live):
    rule(4, "동의어 클러스터링 — 흩어진 표현을 하나의 후보로")
    cmd(f"clustering.cluster_texts(threshold={clustering.DEFAULT_THRESHOLD})")
    vectorstore.init(conn)
    cs = [c for c in clustering.cluster_texts(conn, channel="commerce_rank") if c.size > 1]
    cs.sort(key=lambda c: -c.size)
    shown = 0
    for c in cs:
        if shown >= rows:
            break
        print(f"  {bold('[' + str(c.size) + ']')} {c.canonical[:62]}")
        for m in c.members:
            if m != c.canonical:
                print(dim(f"        {m[:62]}"))
        shown += 1
        print()
    print(hi(f"  묶인 후보 {len(cs)}개 / 전체 색인 {vectorstore.count(conn)}건"))


# ─────────────────────────────────────────── 5. 저장 스키마 실물

def s5(conn, rows, live):
    rule(5, "공통 스키마 — 4개 채널이 한 테이블에")
    cmd("SELECT * FROM signal_raw ORDER BY RANDOM() LIMIT n")
    qs = conn.execute(
        """
        SELECT substr(observed_at,1,10) obs, substr(collected_at,1,10) col,
               channel, substr(keyword_raw,1,18) keyword, substr(entity,1,22) entity,
               metric_type, round(metric_value,1) val
        FROM signal_raw
        WHERE entity <> '' ORDER BY RANDOM() LIMIT ?
        """, (rows,)).fetchall()
    cols = qs[0].keys()
    w = [max(len(c), max(len(str(r[c])) for r in qs)) for c in cols]
    print(dim("  " + "  ".join(c.ljust(x) for c, x in zip(cols, w))))
    for r in qs:
        print("  " + "  ".join(str(r[c]).ljust(x) for c, x in zip(cols, w)))
    print()
    print(hi("  entity 하나로 전체·성별·연령·교차셀·지역·상품을 모두 담는다."))
    print(hi("  세그먼트가 늘어도 스키마를 바꾸지 않는다."))


# ───────────────────────────────────────── 6. 저장 원본 파일

def s6(conn, rows, live):
    rule(6, "저장 원본 — 관측일별 CSV")
    snaps = sorted((ROOT / "data" / "snapshots" / "commerce_rank").glob("*.csv"))
    if not snaps:
        print(dim("  스냅샷 없음"))
        return
    cmd(f"head -{min(rows, 12)} {snaps[-1].relative_to(ROOT)}")
    for line in snaps[-1].read_text(encoding="utf-8").splitlines()[:min(rows, 12)]:
        print(dim("  " + line[:150]))
    print()
    print(hi(f"  스냅샷 {len(snaps)}개. SQLite 는 여기서 다시 만들 수 있는 파생물이다."))
    print(hi("  크롤링은 소급 수집이 안 되므로 원본을 텍스트로도 남긴다."))


# ─────────────────────────────────── 7. 후보 → 상품 매칭 날것

def s7(conn, rows, live):
    rule(7, "후보 → 실제 상품 연결 (벡터 + 어휘)")
    for kw in ("맨투맨", "후드티", "럭비티"):
        cmd(f"features.match_products(conn, '{kw}')")
        try:
            ms = ft.match_products(conn, kw, limit=rows)
        except Exception as exc:
            print(dim(f"  {type(exc).__name__}"))
            continue
        for name, sim, lex in ms:
            ss = f"{sim:.3f}" if sim is not None else "  -  "
            tag = ok("어휘O") if lex else dim("어휘X")
            print(f"  {ss}  {tag}  {dim(name[:62])}")
        if not ms:
            print(hi("  해당 없음 — 수집 범위에 맞는 상품이 없다"))
        print()


SECTIONS = [s1, s2, s3, s4, s5, s6, s7]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=25)
    ap.add_argument("--only", type=int)
    ap.add_argument("--live", action="store_true", help="API 를 실제 호출")
    ap.add_argument("--step", action="store_true")
    a = ap.parse_args(argv)

    conn = storage.connect()
    chosen = [SECTIONS[a.only - 1]] if a.only else SECTIONS
    for i, fn in enumerate(chosen):
        fn(conn, a.rows, a.live)
        if a.step and i < len(chosen) - 1:
            try:
                input(dim("\n  [Enter] "))
            except EOFError:
                pass
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
