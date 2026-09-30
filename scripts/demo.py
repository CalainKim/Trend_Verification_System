#!/usr/bin/env python3
"""미팅용 라이브 데모.

    python scripts/demo.py            # 전체를 이어서 실행
    python scripts/demo.py --step     # 구간마다 멈춤 (발표용)
    python scripts/demo.py --only 3   # 특정 구간만

화면 대신 DB 와 터미널로 보여준다. 실제 질의와 실제 결과를 그대로 띄우므로
"돌아간다"를 말이 아니라 실행으로 보인다.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import demographics as dg, export, features as ft, storage  # noqa: E402

W = 78
C = {"t": "\033[1m", "d": "\033[2m", "g": "\033[32m", "r": "\033[31m",
     "y": "\033[33m", "c": "\033[36m", "0": "\033[0m"}
COLOR = sys.stdout.isatty()


def p(text="", color=None):
    if color and COLOR:
        print(f"{C[color]}{text}{C['0']}")
    else:
        print(text)


def head(n, title):
    print()
    p("━" * W, "d")
    p(f" {n}. {title}", "t")
    p("━" * W, "d")


def sql(query, conn, note=None):
    """질의문을 보여주고 실행 결과를 표로 띄운다."""
    p(textwrap.indent(textwrap.dedent(query).strip(), "  "), "c")
    if note:
        p(f"  ({note})", "d")
    rows = conn.execute(query).fetchall()
    if not rows:
        p("  (결과 없음)", "d")
        return rows
    cols = rows[0].keys()
    widths = [max(len(str(c)), max(len(str(r[c])) for r in rows)) for c in cols]
    print()
    p("  " + "  ".join(str(c).ljust(w) for c, w in zip(cols, widths)), "d")
    for r in rows:
        print("  " + "  ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))
    return rows


def pause(on):
    if on:
        try:
            input("\n  [Enter] ")
        except EOFError:
            pass


# ─────────────────────────────────────────────────────────────── 구간

def s1(conn):
    head(1, "무엇을 얼마나 모았는가")
    sql("""
        SELECT channel, COUNT(*) AS rows_, COUNT(DISTINCT keyword_raw) AS keywords,
               MIN(substr(observed_at,1,10)) AS first_day,
               MAX(substr(observed_at,1,10)) AS last_day
        FROM signal_raw GROUP BY channel ORDER BY channel
    """, conn)
    p("\n  4개 채널이 하나의 테이블에 공통 스키마로 들어간다.", "d")
    p("  채널마다 형식·주기·노이즈 특성이 다르지만 저장은 통일했다.", "d")


def s2(conn):
    head(2, "시점을 두 개로 나눈 이유")
    p("  같은 행의 두 시점을 본다.\n")
    sql("""
        SELECT substr(observed_at,1,10) AS observed_at,
               substr(collected_at,1,10) AS collected_at,
               channel, keyword_raw, metric_value
        FROM signal_raw
        WHERE channel='naver_datalab' AND observed_at < '2022-01-01'
        LIMIT 3
    """, conn)
    p("\n  2021년 자료를 2026년에 수집했다.", "y")
    p("  시점이 한 컬럼이면 이 행들이 전부 '오늘 관측'으로 기록된다.", "y")
    p("  그러면 판단 기준 시점 이전만 고르는 필터가 아무것도 거르지 못한다.", "y")


def s3(conn):
    head(3, "누수 차단이 실제로 막는가")
    case = conn.execute("SELECT * FROM trend_case LIMIT 1").fetchone()
    if not case:
        p("  등록된 케이스가 없다.", "d")
        return
    kw, t_cut = case["keyword"], case["t_cut"]
    p(f"  사례 '{kw}' · 판단 기준 시점 T_cut = {t_cut}\n")

    total = conn.execute(
        "SELECT COUNT(*) c FROM signal_raw WHERE keyword_raw=?", (kw,)).fetchone()["c"]
    before = conn.execute(
        "SELECT COUNT(*) c FROM signal_raw WHERE keyword_raw=? AND observed_at<?",
        (kw, t_cut)).fetchone()["c"]
    p(f"  DB 전체 {total:,}행 중 T_cut 이전은 {before:,}행", "d")

    rows = export.fetch_before_cut(conn, t_cut, [kw])
    p(f"  내보내기 조회 결과 {len(rows):,}행 — 경계 이후는 포함되지 않는다", "g")

    p("\n  이제 일부러 T_cut 이후 자료를 섞어 검증기를 통과시켜 본다.", "y")
    poisoned = list(rows) + [{"observed_at": "2099-01-01"}]
    try:
        export.assert_no_leakage(poisoned, t_cut)
        p("  통과해버렸다 (검증기가 동작하지 않음)", "r")
    except export.LeakageError as exc:
        p(f"  차단됨: {str(exc)[:70]}", "g")
    p("\n  산출물 생성 직전에 한 번 더 확인한다. 한 건이라도 어기면 전체가 중단된다.", "d")


def s4(conn):
    head(4, "인구통계는 왜 그대로 쓰면 안 되는가")
    cat = "50000169"
    base = dg.daily_shares(conn, f"category:{cat}", "age")
    if not base:
        p("  기준선 자료가 없다.", "d")
        return
    p("  남성의류>티셔츠 분야 전체의 연령 분포 (기준선)\n")
    for g in sorted(base):
        p(f"    {g}대  {base[g]:6.1%}  {'█' * int(base[g] * 60)}")
    p("\n  어떤 키워드를 조회해도 40대가 최다로 나온다.", "y")
    p("  네이버쇼핑 이용자층의 특성이지 키워드의 특성이 아니다.", "y")
    p("\n  기준선 대비 비율(리프트)로 환산하면 이렇게 갈린다.\n")
    for kw in ("반팔티", "맨투맨", "정장"):
        sk = dg.profile(conn, kw, cat, prefix="age")
        if not sk:
            continue
        top = dg.concentration(sk)
        twenties = next((s for s in sk if s.group == "20"), None)
        p(f"    {kw:<6} 20대 {twenties.lift:>5.2f}   최대 {top:>5.2f}"
          + ("   쏠림 없음" if top < 1.5 else "   특정 연령에 집중"))


def s5(conn):
    head(5, "해외가 먼저인가 — 가설을 자료로 확인")
    found = False
    for kw in ("맨투맨", "후드티"):
        for geo in ("US",):
            ll = ft.lead_lag(conn, kw, "2026-09-01", geo, window_days=600)
            if not ll:
                continue
            found = True
            who = "해외 선행" if ll.lead_days > 0 else "한국 선행"
            flag = ("  경계에 걸림, 근거 불가" if ll.at_boundary
                    else ("" if ll.reliable else "  상관 낮음, 근거 불가"))
            p(f"  {kw:<6} vs {geo}   {who} {abs(ll.lead_days)}일 · "
              f"상관 {ll.correlation}{flag}")
    if not found:
        p("  Google Trends 자료가 없다.", "d")
        return
    p("\n  계획서가 전제한 '유행은 해외에서 넘어온다'와 방향이 반대다.", "y")
    p("  다만 둘 다 계절 상품이라 계절 검색 시점 차이일 수 있다.", "d")
    p("  이 수치만으로 가설을 반박하지 않고, 계절성 통제 후 재확인한다.", "d")


def s6(conn):
    head(6, "후보와 실제 상품을 잇는다")
    p("  후보는 검색어이고 커머스 자료는 상품명이라 문자열로는 이어지지 않는다.\n")
    for kw in ("맨투맨", "럭비티"):
        try:
            ms = ft.match_products(conn, kw, limit=3)
        except Exception as exc:
            p(f"  {kw}: 색인 없음 ({type(exc).__name__})", "d")
            continue
        p(f"  '{kw}' → {len(ms)}건")
        for name, sim, lex in ms[:3]:
            ss = f"{sim:.3f}" if sim is not None else "  -  "
            p(f"      {ss}  {name[:52]}", "d")
        if not ms:
            p("      해당 없음 — 수집 범위에 맞는 상품이 없다는 뜻", "d")
    p("\n  맞는 상품이 없으면 '없음'이 나와야 한다. 억지로 채우면 판정이 오염된다.", "d")


def s7(conn):
    head(7, "검증 파트에 넘기는 것")
    case_dir = ROOT / "cases" / "case_pilot_rugby"
    if not case_dir.exists():
        p("  케이스 번들이 없다.", "d")
        return
    for f in sorted(case_dir.iterdir()):
        p(f"  {f.name:<22} {f.stat().st_size:>10,} bytes")
    meta = (case_dir / "meta.json").read_text(encoding="utf-8")
    p("\n  meta.json 내용", "d")
    p(textwrap.indent(meta.strip(), "    "), "d")
    p("\n  정답 라벨과 피크 시점은 의도적으로 빠져 있다 (블라인드).", "g")
    row = conn.execute("SELECT label, label_reason FROM trend_case LIMIT 1").fetchone()
    if row:
        p(f"  정답은 수집 파트만 보관한다 → label={row['label']}", "d")


SECTIONS = [s1, s2, s3, s4, s5, s6, s7]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="미팅용 라이브 데모")
    ap.add_argument("--step", action="store_true", help="구간마다 멈춤")
    ap.add_argument("--only", type=int, help="특정 구간만 (1~7)")
    args = ap.parse_args(argv)

    conn = storage.connect()
    p("\n트렌드 시그널 검증 시스템 — 수집 파트 데모", "t")
    p(f"DB: {storage.DEFAULT_DB_PATH.relative_to(ROOT)}", "d")

    chosen = [SECTIONS[args.only - 1]] if args.only else SECTIONS
    for i, fn in enumerate(chosen):
        fn(conn)
        if i < len(chosen) - 1:
            pause(args.step)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
