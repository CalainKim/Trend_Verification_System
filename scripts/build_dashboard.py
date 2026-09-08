#!/usr/bin/env python3
"""정적 대시보드 생성. docs/index.html 을 만들고 GitHub Pages 가 서빙한다.

    python scripts/build_dashboard.py

의존성 없이 인라인 SVG 로 그린다. 외부 CDN 을 쓰지 않으므로 네트워크가 막힌
환경에서도 그대로 열린다.
"""

from __future__ import annotations

import html
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import analytics, storage  # noqa: E402

KST = timezone(timedelta(hours=9))
OUT = ROOT / "docs" / "index.html"

# dataviz 기본 팔레트 슬롯 1~3 (all-pairs 검증 통과: light/dark 양쪽)
SERIES = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70")]

CSS = """
:root {
  color-scheme: light;
  --page:        #f9f9f7;
  --surface:     #fcfcfb;
  --ink:         #0b0b0b;
  --ink-2:       #52514e;
  --muted:       #898781;
  --grid:        #e1e0d9;
  --axis:        #c3c2b7;
  --border:      rgba(11,11,11,0.10);
  --good:        #0ca30c;
  --warning:     #fab219;
  --critical:    #d03b3b;
  --up:          #006300;
  --series-1:    #2a78d6;
  --series-2:    #eb6834;
  --series-3:    #1baf7a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page:      #0d0d0d;
    --surface:   #1a1a19;
    --ink:       #ffffff;
    --ink-2:     #c3c2b7;
    --muted:     #898781;
    --grid:      #2c2c2a;
    --axis:      #383835;
    --border:    rgba(255,255,255,0.10);
    --good:      #0ca30c;
    --warning:   #fab219;
    --critical:  #d03b3b;
    --up:        #0ca30c;
    --series-1:  #3987e5;
    --series-2:  #d95926;
    --series-3:  #199e70;
  }
}
:root[data-theme="dark"] {
    color-scheme: dark;
    --page:      #0d0d0d;
    --surface:   #1a1a19;
    --ink:       #ffffff;
    --ink-2:     #c3c2b7;
    --muted:     #898781;
    --grid:      #2c2c2a;
    --axis:      #383835;
    --border:    rgba(255,255,255,0.10);
    --good:      #0ca30c;
    --warning:   #fab219;
    --critical:  #d03b3b;
    --up:        #0ca30c;
    --series-1:  #3987e5;
    --series-2:  #d95926;
    --series-3:  #199e70;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font: 14px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
}
.wrap { max-width: 1000px; margin: 0 auto; padding: 32px 20px 72px; }
h1 { font-size: 21px; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 15px; margin: 0 0 2px; }
.sub { color: var(--ink-2); font-size: 13px; margin: 0; }
.note { color: var(--muted); font-size: 12.5px; margin: 6px 0 0; }
section { margin-top: 28px; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 20px; margin-top: 10px;
}
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 14px; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.kpi .label { color: var(--muted); font-size: 12px; }
.kpi .value { font-size: 26px; line-height: 1.2; margin-top: 2px; }
.kpi .value.warn { color: var(--critical); }
.strip { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.day {
  border: 1px solid var(--border); border-radius: 7px; padding: 7px 10px;
  min-width: 92px; background: var(--surface);
}
.day .d { font-size: 11.5px; color: var(--muted); font-variant-numeric: tabular-nums; }
.day .s { font-size: 12.5px; margin-top: 2px; display: flex; align-items: center; gap: 5px; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.dot.ok { background: var(--good); }
.dot.miss { background: var(--critical); }
.day.miss { border-color: var(--critical); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-weight: 600; color: var(--muted); font-size: 12px;
     padding: 0 10px 7px 0; border-bottom: 1px solid var(--grid); white-space: nowrap; }
td { padding: 8px 10px 8px 0; border-bottom: 1px solid var(--grid); vertical-align: top; }
tr:last-child td { border-bottom: none; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: var(--up); }
.down { color: var(--critical); }
.tag { font-size: 11px; border: 1px solid var(--border); border-radius: 4px;
       padding: 1px 5px; color: var(--ink-2); white-space: nowrap; }
.tag.soldout { color: var(--critical); border-color: var(--critical); }
a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--border); }
a:hover { border-bottom-color: var(--ink-2); }
.scroll { overflow-x: auto; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; margin: 0 0 10px; font-size: 12.5px; color: var(--ink-2); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.swatch { width: 14px; height: 3px; border-radius: 2px; flex: none; }
.banner {
  border: 1px solid var(--warning); border-left-width: 3px; border-radius: 8px;
  padding: 10px 14px; margin-top: 10px; font-size: 13px; color: var(--ink-2);
  background: var(--surface);
}
.banner strong { color: var(--ink); }
#tip {
  position: fixed; pointer-events: none; opacity: 0; transition: opacity .1s;
  background: var(--surface); color: var(--ink); border: 1px solid var(--border);
  border-radius: 7px; padding: 7px 10px; font-size: 12.5px; max-width: 280px;
  box-shadow: 0 4px 14px rgba(0,0,0,.12); z-index: 20;
}
footer { margin-top: 40px; color: var(--muted); font-size: 12px; line-height: 1.7; }
"""

JS = """
(function () {
  var tip = document.getElementById('tip');
  function show(e, t) {
    tip.textContent = t; tip.style.opacity = 1;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + tip.offsetWidth > innerWidth - 8) x = e.clientX - tip.offsetWidth - 14;
    if (y + tip.offsetHeight > innerHeight - 8) y = e.clientY - tip.offsetHeight - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  document.querySelectorAll('[data-tip]').forEach(function (el) {
    el.addEventListener('pointerenter', function (e) { show(e, el.dataset.tip); });
    el.addEventListener('pointermove', function (e) { show(e, el.dataset.tip); });
    el.addEventListener('pointerleave', function () { tip.style.opacity = 0; });
  });
})();
"""


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def rank_chart(days, items, highlights, max_rank: int = 100) -> str:
    """순위 추이. 강조 형식 - 주목할 3개만 색을 주고 나머지는 배경으로 깐다."""
    if len(days) < 2:
        return ('<p class="note">추이를 그리려면 관측일이 2일 이상 필요하다. '
                '하루 더 쌓이면 나타난다.</p>')

    W, H = 760, 340
    L, R, T, B = 46, 128, 16, 34
    pw, ph = W - L - R, H - T - B

    def x(i):
        return L + (pw * i / max(1, len(days) - 1))

    def y(rank):  # 1위가 위로 가도록 뒤집는다
        return T + ph * (rank - 1) / max(1, max_rank - 1)

    parts = [
        f'<svg viewBox="0 0 {W} {H}" width="100%" height="auto" '
        f'style="min-width:620px;display:block" role="img" '
        f'aria-label="상품별 순위 추이">'
    ]
    for rank in (1, 25, 50, 75, 100):
        yy = round(y(rank), 1)
        parts.append(f'<line x1="{L}" y1="{yy}" x2="{L+pw}" y2="{yy}" '
                     f'stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{L-9}" y="{yy+4}" text-anchor="end" font-size="11" '
                     f'fill="var(--muted)">{rank}위</text>')
    for i, d in enumerate(days):
        parts.append(f'<text x="{round(x(i),1)}" y="{H-12}" text-anchor="middle" '
                     f'font-size="11" fill="var(--muted)">{esc(d[5:])}</text>')

    hi_keys = {it.key for it in highlights}
    context = [it for it in items.values()
               if it.key not in hi_keys and all(d in it.ranks for d in days)]
    for it in context[:70]:
        pts = " ".join(f"{round(x(i),1)},{round(y(it.ranks[d]),1)}" for i, d in enumerate(days))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="var(--axis)" '
                     f'stroke-width="1" opacity="0.35" data-tip="{esc(it.name)}"/>')

    shown = highlights[:3]
    for n, it in enumerate(shown):
        color = f"var(--series-{n+1})"
        pts = " ".join(f"{round(x(i),1)},{round(y(it.ranks[d]),1)}"
                       for i, d in enumerate(days) if d in it.ranks)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                     f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, d in enumerate(days):
            if d not in it.ranks:
                continue
            tip = f"{it.brand} · {it.name} — {d} {it.ranks[d]}위"
            parts.append(f'<circle cx="{round(x(i),1)}" cy="{round(y(it.ranks[d]),1)}" r="4.5" '
                         f'fill="{color}" stroke="var(--surface)" stroke-width="2" '
                         f'data-tip="{esc(tip)}"/>')

    # 직접 라벨. 끝점이 가까우면 글자가 겹치므로 최소 간격만큼 벌린다.
    last = days[-1]
    placed = sorted(
        ((y(it.ranks[last]), n, it) for n, it in enumerate(shown) if last in it.ranks),
        key=lambda t: t[0],
    )
    gap, prev = 15.0, None
    for anchor, n, it in placed:
        ly = anchor if prev is None else max(anchor, prev + gap)
        prev = ly
        lx = x(len(days) - 1) + 10
        if abs(ly - anchor) > 1.5:  # 밀어냈으면 어느 점의 라벨인지 선으로 이어준다
            parts.append(f'<path d="M{round(lx-6,1)},{round(anchor,1)} L{round(lx-2,1)},'
                         f'{round(ly-4,1)}" stroke="var(--axis)" stroke-width="1" fill="none"/>')
        label = it.name if len(it.name) <= 16 else it.name[:15] + "…"
        parts.append(f'<text x="{round(lx,1)}" y="{round(ly,1)}" dominant-baseline="middle" '
                     f'font-size="11.5" fill="var(--ink)">{esc(label)}</text>')
    parts.append("</svg>")

    legend = ['<div class="legend">']
    for n, it in enumerate(highlights[:3]):
        legend.append(f'<span><i class="swatch" style="background:var(--series-{n+1})"></i>'
                      f'{esc(it.brand)} · {esc(it.name[:22])}</span>')
    legend.append('<span><i class="swatch" style="background:var(--axis)"></i>'
                  '그 외 추적 상품</span></div>')
    return "".join(legend) + '<div class="scroll">' + "".join(parts) + "</div>"


def mover_table(items, first, last, kind) -> str:
    if not items:
        return '<p class="note">해당 없음</p>'
    head = "신규 순위" if kind == "new" else "순위 변화"
    rows = []
    for it in items:
        if kind == "new":
            change = f'<td class="num">{it.ranks[last]}위</td>'
            review = it.reviews.get(last)
            rv = f"{review:,}" if review is not None else "-"
        else:
            d = it.rank_delta(first, last) or 0
            cls, arrow = ("up", "▲") if d > 0 else ("down", "▼")
            change = (f'<td class="num {cls}">{arrow}{abs(d)}'
                      f'<span style="color:var(--muted)"> {it.ranks[first]}→{it.ranks[last]}</span></td>')
            g = it.review_delta(first, last)
            rv = f"{g:+,}" if g is not None else "-"
        name = (f'<a href="{esc(it.url)}" target="_blank" rel="noopener">{esc(it.name)}</a>'
                if it.url else esc(it.name))
        tag = ' <span class="tag soldout">품절</span>' if it.sold_out else ""
        rows.append(f"<tr>{change}<td>{esc(it.brand)}</td><td>{name}{tag}</td>"
                    f'<td>{esc(it.category)}</td><td class="num">{rv}</td></tr>')
    return (f'<div class="scroll"><table><thead><tr><th>{head}</th><th>브랜드</th>'
            f"<th>상품</th><th>분류</th><th>리뷰</th></tr></thead>"
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def build(conn, top: int = 10) -> str:
    cov = analytics.coverage(conn, "commerce_rank")
    days, items = analytics.build_items(conn)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    missing = [c for c in cov if c.missing]
    last_snapshot = cov[-1].day if cov else "-"

    strip = []
    for c in cov:
        if c.missing:
            strip.append(f'<div class="day miss"><div class="d">{esc(c.day)}</div>'
                         f'<div class="s"><i class="dot miss"></i>결측</div></div>')
        else:
            strip.append(f'<div class="day"><div class="d">{esc(c.day)}</div>'
                         f'<div class="s"><i class="dot ok"></i>수집 {c.n_snapshots}회</div></div>')

    kpis = [
        ("누적 관측일", f"{len(cov) - len(missing)}일", False),
        ("결측일", f"{len(missing)}일", bool(missing)),
        ("추적 상품", f"{len(items):,}개", False),
        ("최근 수집", last_snapshot, False),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="label">{esc(l)}</div>'
        f'<div class="value{" warn" if w else ""}">{esc(v)}</div></div>'
        for l, v, w in kpis
    )

    body = [f'<div class="kpis">{kpi_html}</div>']
    body.append('<section><h2>수집 현황</h2>'
                '<p class="sub">크롤링은 소급 수집이 불가능하다. 결측일은 영구 손실이다.</p>'
                f'<div class="card"><div class="strip">{"".join(strip)}</div></div></section>')

    if len(days) >= 2:
        first, last = days[0], days[-1]
        span = (date.fromisoformat(last) - date.fromisoformat(first)).days
        risers, fallers, new = analytics.movers(items, first, last, top=top)
        body.append(f'<section><h2>순위 추이</h2><p class="sub">{esc(first)} → {esc(last)} '
                    f'· 급상승 상위 3개를 강조했다. 선에 마우스를 올리면 상품명이 나온다.</p>'
                    f'<div class="card">{rank_chart(days, items, risers)}</div></section>')
        body.append(f'<section><h2>순위 급상승</h2><div class="card">'
                    f'{mover_table(risers, first, last, "up")}</div></section>')
        body.append(f'<section><h2>순위 급하락</h2><div class="card">'
                    f'{mover_table(fallers, first, last, "down")}</div></section>')
        body.append(f'<section><h2>신규 진입</h2><p class="sub">{esc(first)}에는 100위 안에 '
                    f'없다가 {esc(last)}에 진입한 상품.</p><div class="card">'
                    f'{mover_table(new, first, last, "new")}</div></section>')

        contra = analytics.contradiction_signals(items, first, last)
        warn = ""
        if span < analytics.MIN_REVIEW_WINDOW_DAYS:
            warn = (f'<div class="banner"><strong>아직 읽을 수 없는 신호다.</strong> '
                    f'관측 구간이 {span}일뿐이라 리뷰가 거의 움직이지 않는다. 급상승 상품 '
                    f'대부분이 자동으로 걸리므로 {analytics.MIN_REVIEW_WINDOW_DAYS}일 이상 '
                    f'쌓인 뒤에 봐야 한다.</div>')
        body.append('<section><h2>반증 신호 · 순위는 올랐는데 리뷰가 늘지 않음</h2>'
                    '<p class="sub">리뷰는 실제 구매를 거쳐야 쌓이므로 조작 여지가 적다. '
                    '순위만 오르고 리뷰가 붙지 않으면 광고 노출이나 프로모션 효과를 의심할 '
                    '근거가 된다.</p>'
                    f'{warn}<div class="card">{mover_table(contra[:top], first, last, "up")}'
                    '</div></section>')
    else:
        body.append('<section><div class="card"><p class="note">비교할 날이 아직 부족하다. '
                    '하루 더 쌓이면 순위 변화가 나온다.</p></div></section>')

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>트렌드 시그널 수집 현황</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<h1>트렌드 시그널 수집 현황</h1>
<p class="sub">29CM 상의 카테고리 랭킹 · 트랙 B 실시간 축적분</p>
<p class="note">생성 {esc(now)}</p>
{"".join(body)}
<footer>
데이터 출처 29CM 베스트 랭킹 (여성의류&gt;상의, 남성의류&gt;상의 각 100위)<br>
이 페이지는 관측된 사실만 보여준다. 트렌드 후보의 확정·보류·기각 판정은 별도 검증 단계의 몫이다.<br>
하루에 여러 번 수집하더라도 일 단위 집계에는 그날의 마지막 스냅샷 하나만 쓴다.<br>
<a href="https://github.com/CalainKim/Trend_Verification_System">저장소</a>
</footer>
</div><div id="tip" role="status"></div>
<script>{JS}</script></body></html>
"""


def main() -> int:
    conn = storage.connect()
    storage.init_db(conn)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (OUT.parent / ".nojekyll").write_text("", encoding="utf-8")
    OUT.write_text(build(conn), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} 생성 ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
