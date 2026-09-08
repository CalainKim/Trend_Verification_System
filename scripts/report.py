#!/usr/bin/env python3
"""터미널 수집 리포트.

    python scripts/report.py              # 전체
    python scripts/report.py --no-color   # 색 없이 (CI 로그용)
    python scripts/report.py --top 5

판정은 하지 않는다. 무엇이 관측됐는지와, 검증 단계로 넘길 반증 후보만 표시한다.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import analytics, storage  # noqa: E402

C = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "good": "\033[32m", "bad": "\033[31m", "warn": "\033[33m", "info": "\033[36m",
}


def width(s: str) -> int:
    """한글은 터미널에서 두 칸을 차지한다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s: str, n: int) -> str:
    s = trim(s, n)
    return s + " " * max(0, n - width(s))


def trim(s: str, n: int) -> str:
    if width(s) <= n:
        return s
    out = ""
    for ch in s:
        if width(out) + width(ch) > n - 1:
            return out + "…"
        out += ch
    return out


def paint(s: str, color: str, enabled: bool) -> str:
    return f"{C[color]}{s}{C['reset']}" if enabled and color in C else s


def section(title: str, color: bool) -> None:
    print()
    print(paint(title, "bold", color))
    print(paint("─" * 74, "dim", color))


def render_coverage(conn, color: bool) -> None:
    rows = analytics.coverage(conn, "commerce_rank")
    section("수집 현황", color)
    if not rows:
        print("  수집된 데이터가 없다.")
        return
    missing = [r for r in rows if r.missing]
    for r in rows:
        if r.missing:
            mark = paint("결측", "bad", color)
            bar = paint("─" * 3, "bad", color)
            print(f"  {r.day}  {bar}  {mark}  (소급 수집 불가)")
        else:
            bar = paint("●" * r.n_snapshots, "good", color)
            print(f"  {r.day}  {pad(bar, 3 + (len(C['good']) + len(C['reset'])) * color)}"
                  f"  정상  스냅샷 {r.n_snapshots}개 · {r.n_rows:,}행")
    total = len(rows)
    ok = total - len(missing)
    line = f"  누적 {total}일 중 수집 {ok}일 · 결측 {len(missing)}일"
    print(paint(line, "warn" if missing else "dim", color))


def render_items(title, items, days, color, kind, top) -> None:
    first, last = days[0], days[-1]
    section(title, color)
    if not items:
        print("  해당 없음")
        return
    print(paint(f"  {'순위변화':<8} {pad('브랜드', 14)} {pad('상품', 34)} {'리뷰':>8}", "dim", color))
    for it in items[:top]:
        if kind == "new":
            change = f"신규 {it.ranks[last]:>3}위"
            change = paint(pad(change, 12), "info", color)
            review = it.reviews.get(last)
            rv = f"{review:,}" if review is not None else "-"
        else:
            d = it.rank_delta(first, last) or 0
            arrow = "▲" if d > 0 else "▼"
            change = f"{arrow}{abs(d):<3} {it.ranks[first]:>3}→{it.ranks[last]:<3}"
            change = paint(pad(change, 12), "good" if d > 0 else "bad", color)
            g = it.review_delta(first, last)
            rv = f"+{g:,}" if g is not None else "-"
        flag = paint(" 품절", "warn", color) if it.sold_out else ""
        print(f"  {change} {pad(it.brand, 14)} {pad(it.name, 34)} {rv:>8}{flag}")


def render_contradictions(items, days, color, top) -> None:
    from datetime import date

    first, last = days[0], days[-1]
    span_days = (date.fromisoformat(last) - date.fromisoformat(first)).days
    found = analytics.contradiction_signals(items, first, last)
    section("반증 신호  순위는 올랐는데 리뷰가 늘지 않음", color)
    print(paint("  리뷰는 실제 구매를 거쳐야 쌓인다. 순위만 오르고 리뷰가 붙지 않으면", "dim", color))
    print(paint("  광고 노출이나 프로모션 효과를 의심할 근거가 된다.", "dim", color))
    if span_days < analytics.MIN_REVIEW_WINDOW_DAYS:
        print()
        print(paint(
            f"  주의  관측 구간이 {span_days}일뿐이라 이 신호는 아직 의미가 없다. "
            f"리뷰는 느리게 쌓여서", "warn", color))
        print(paint(
            f"        대부분의 상품이 자동으로 걸린다. {analytics.MIN_REVIEW_WINDOW_DAYS}일 이상 "
            f"쌓인 뒤에 봐야 한다.", "warn", color))
    print()
    if not found:
        print("  해당 없음")
        return
    for it in found[:top]:
        d = it.rank_delta(first, last) or 0
        g = it.review_delta(first, last)
        mark = paint("주의", "warn", color)
        print(f"  {mark}  ▲{d:<3} {it.ranks[first]:>3}→{it.ranks[last]:<3} "
              f"{pad(it.brand, 12)} {pad(it.name, 32)} 리뷰 {g:+d}")
    if len(found) > top:
        print(paint(f"  … 외 {len(found) - top}건", "dim", color))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="수집 데이터 터미널 리포트")
    p.add_argument("--db", default=None)
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    color = not args.no_color and sys.stdout.isatty()
    conn = storage.connect(Path(args.db) if args.db else None)
    storage.init_db(conn)

    render_coverage(conn, color)

    days, items = analytics.build_items(conn)
    if len(days) < 2:
        print()
        print("  비교할 날이 아직 부족하다. 하루 더 쌓이면 순위 변화가 나온다.")
        return 0

    risers, fallers, new = analytics.movers(items, days[0], days[-1], top=args.top)
    span = f"({days[0]} → {days[-1]})"
    render_items(f"순위 급상승 {span}", risers, days, color, "up", args.top)
    render_items(f"순위 급하락 {span}", fallers, days, color, "down", args.top)
    render_items(f"신규 진입 {span}", new, days, color, "new", args.top)
    render_contradictions(items, days, color, args.top)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
