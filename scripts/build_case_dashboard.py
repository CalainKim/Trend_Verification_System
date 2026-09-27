#!/usr/bin/env python3
"""케이스 분석 화면 생성. docs/cases.html 을 만든다.

수집 현황(index.html)이 파이프라인이 도는지 보는 화면이라면, 이쪽은
연구 결과를 보는 화면이다. 케이스별로 T_cut 시점에 무엇이 관측됐는지를
채널별 추이와 인구통계 쏠림으로 보여준다.

발표에서 쓰는 화면이므로 수치를 좋게 보이도록 다듬지 않는다. 신호가 없으면
없다고 보여야 T_cut 설정이 적절했는지 판단할 수 있다.
"""

from __future__ import annotations

import html
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import demographics as dg, features as ft, storage, webtheme  # noqa: E402

KST = timezone(timedelta(hours=9))
OUT = ROOT / "docs" / "cases.html"
CONTEXT_DAYS = 180          # 차트에 보여줄 T_cut 이전 구간


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def fmt(v, digits=2, suffix=""):
    return "—" if v is None else f"{v:.{digits}f}{suffix}"


def series(conn, keyword, channel, entity, start, end, metric):
    rows = conn.execute(
        """
        SELECT observed_at, AVG(metric_value) v FROM signal_raw
        WHERE keyword_raw=? AND channel=? AND entity=? AND metric_type=?
          AND observed_at>=? AND observed_at<?
        GROUP BY observed_at ORDER BY observed_at
        """, (keyword, channel, entity, metric, start, end)).fetchall()
    return [(r["observed_at"][:10], r["v"]) for r in rows]


SMOOTH_DAYS = 7


def smooth(points, window=SMOOTH_DAYS):
    """이동평균. 일별 정규화 지수는 노이즈가 커서 추세가 묻힌다.

    원본을 버리지 않고 선만 부드럽게 그린다. 실제 값은 툴팁에 남긴다.
    """
    out = []
    for i in range(len(points)):
        lo = max(0, i - window + 1)
        chunk = [v for _, v in points[lo:i + 1]]
        out.append((points[i][0], sum(chunk) / len(chunk), points[i][1]))
    return out


def line_chart(named_series, t_cut) -> str:
    """채널별 추이. 정규화 기준이 달라 값의 크기는 비교하지 않는다.
    각 시리즈를 자기 최댓값으로 맞춰 모양만 견준다."""
    named_series = [(n, s) for n, s in named_series if len(s) >= 5]
    if not named_series:
        return '<p class="note">차트를 그릴 만큼 자료가 없다.</p>'

    days = sorted({d for _, s in named_series for d, _ in s})
    idx = {d: i for i, d in enumerate(days)}
    W, H, L, R, T, B = 820, 250, 44, 96, 14, 30
    pw, ph = W - L - R, H - T - B

    def x(d): return L + pw * idx[d] / max(1, len(days) - 1)
    def y(v): return T + ph * (1 - v)

    p = [f'<svg viewBox="0 0 {W} {H}" width="100%" height="auto" '
         f'style="min-width:640px;display:block" role="img" aria-label="채널별 추이">']
    for frac, lab in ((0.0, "최대"), (0.5, "중간"), (1.0, "0")):
        yy = round(y(1 - frac), 1)
        p.append(f'<line x1="{L}" y1="{yy}" x2="{L+pw}" y2="{yy}" '
                 f'stroke="var(--grid)" stroke-width="1"/>')
        p.append(f'<text x="{L-8}" y="{yy+4}" text-anchor="end" font-size="10.5" '
                 f'fill="var(--muted)">{lab}</text>')
    for d in (days[0], days[len(days)//2], days[-1]):
        p.append(f'<text x="{round(x(d),1)}" y="{H-10}" text-anchor="middle" '
                 f'font-size="10.5" fill="var(--muted)">{esc(d[2:])}</text>')

    anchors = []
    for n, (name, s) in enumerate(named_series):
        color = f"var(--series-{n+1})"
        sm = smooth(s)
        peak = max(v for _, v, _ in sm) or 1.0
        pts = " ".join(f"{round(x(d),1)},{round(y(v/peak),1)}" for d, v, _ in sm)
        p.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                 f'stroke-width="2" stroke-linejoin="round"/>')
        for d, v, raw in sm:
            p.append(f'<circle cx="{round(x(d),1)}" cy="{round(y(v/peak),1)}" r="6" '
                     f'fill="transparent" data-tip="{esc(name)} · {esc(d)} · '
                     f'원본 {raw:.1f} · {SMOOTH_DAYS}일평균 {v:.1f}"/>')
        anchors.append((y(sm[-1][1] / peak), name))

    # 끝점이 가까우면 라벨이 겹친다. 최소 간격만큼 벌린다.
    prev = None
    for ay, name in sorted(anchors):
        ly = ay if prev is None else max(ay, prev + 15)
        prev = ly
        lx = L + pw + 8
        if abs(ly - ay) > 1.5:
            p.append(f'<path d="M{round(lx-6,1)},{round(ay,1)} L{round(lx-2,1)},'
                     f'{round(ly-4,1)}" stroke="var(--axis)" stroke-width="1" fill="none"/>')
        p.append(f'<text x="{round(lx,1)}" y="{round(ly,1)}" dominant-baseline="middle" '
                 f'font-size="11.5" fill="var(--ink)">{esc(name)}</text>')

    p.append(f'<line x1="{L+pw}" y1="{T}" x2="{L+pw}" y2="{T+ph}" '
             f'stroke="var(--axis)" stroke-width="1" stroke-dasharray="3 3"/>')
    p.append(f'<text x="{L+pw-4}" y="{T+11}" text-anchor="end" font-size="10.5" '
             f'fill="var(--muted)">T_cut {esc(t_cut)}</text>')
    p.append("</svg>")

    legend = ['<div class="legend">']
    for n, (name, _) in enumerate(named_series):
        legend.append(f'<span><i class="swatch" style="background:var(--series-{n+1})">'
                      f'</i>{esc(name)}</span>')
    legend.append('</div>')
    return ("".join(legend) + '<div class="scroll">' + "".join(p) + "</div>"
            + f'<p class="note">각 시리즈를 자기 최댓값으로 맞춰 모양만 비교한다. '
              f'채널마다 정규화 기준이 달라 값의 크기는 비교할 수 없다. '
              f'선은 {SMOOTH_DAYS}일 이동평균이며 원본 값은 점 위에 올리면 나온다.</p>')


def lift_chart(skews) -> str:
    """기준선(1.0) 위아래로 갈리는 값이라 발산형으로 그린다."""
    usable = [s for s in skews if s.reliable]
    if not usable:
        return '<p class="note">기준선이 희소해 리프트를 신뢰할 수 없다.</p>'
    order = sorted(usable, key=lambda s: s.group)
    W, rowh, L = 660, 26, 54
    H = rowh * len(order) + 24
    mid = L + (W - L - 90) / 2
    scale = (W - L - 90) / 2 / max(1.0, max(abs(s.lift - 1) for s in order))

    p = [f'<svg viewBox="0 0 {W} {H}" width="100%" height="auto" '
         f'style="min-width:520px;display:block" role="img" aria-label="연령별 리프트">']
    p.append(f'<line x1="{mid}" y1="6" x2="{mid}" y2="{H-18}" '
             f'stroke="var(--axis)" stroke-width="1"/>')
    p.append(f'<text x="{mid}" y="{H-4}" text-anchor="middle" font-size="10.5" '
             f'fill="var(--muted)">기준선 1.00 (분야 평균)</text>')
    for i, s in enumerate(order):
        yy = 6 + i * rowh
        delta = s.lift - 1
        w = abs(delta) * scale
        x0 = mid if delta >= 0 else mid - w
        color = "var(--pos)" if delta >= 0 else "var(--neg)"
        p.append(f'<text x="{L-10}" y="{yy+15}" text-anchor="end" font-size="11.5" '
                 f'fill="var(--ink-2)">{esc(s.group)}대</text>')
        p.append(f'<rect x="{round(x0,1)}" y="{yy+4}" width="{round(max(w,1),1)}" '
                 f'height="14" rx="3" fill="{color}" '
                 f'data-tip="{esc(s.group)}대 · 점유 {s.observed_share:.1%} · '
                 f'기준 {s.baseline_share:.1%} · 리프트 {s.lift:.2f}"/>')
        lx = (x0 + w + 8) if delta >= 0 else (x0 - 8)
        anchor = "start" if delta >= 0 else "end"
        p.append(f'<text x="{round(lx,1)}" y="{yy+16}" text-anchor="{anchor}" '
                 f'font-size="11" fill="var(--ink)">{s.lift:.2f}</text>')
    p.append("</svg>")
    return '<div class="scroll">' + "".join(p) + "</div>"


def case_section(conn, case) -> str:
    kw, t_cut = case["keyword"], case["t_cut"]
    start = (date.fromisoformat(t_cut) - timedelta(days=CONTEXT_DAYS)).isoformat()
    cat = "50000169"

    chans = [("검색", series(conn, kw, "naver_datalab", "", start, t_cut, "search_index")),
             ("쇼핑 클릭", series(conn, kw, "naver_shopping", "", start, t_cut, "click_index")),
             ("검색 20대男", series(conn, kw, "naver_datalab", "gender=m;ages=3+4",
                                  start, t_cut, "search_index"))]
    feats = ft.extract(conn, kw, t_cut, shopping_category=cat,
                       segment_entity="gender=m;ages=3+4")
    PRETTY = {"검색": "검색", "쇼핑클릭": "쇼핑 클릭",
              "검색·gender=m;ages=3+4": "검색 20대男"}
    age = dg.profile(conn, kw, cat, prefix="age")

    rows = []
    for label, t in feats.channels.items():
        label = PRETTY.get(label, label)
        arrow = ""
        if t.change_ratio is not None:
            cls = "up" if t.change_ratio > 1 else "down"
            arrow = f'<span class="{cls}">{"▲" if t.change_ratio > 1 else "▼"}</span> '
        rows.append(
            f"<tr><td>{esc(label)}</td>"
            f'<td class="num">{arrow}{fmt(t.change_ratio)}</td>'
            f'<td class="num">{fmt(t.slope)}</td>'
            f'<td class="num">{t.coverage:.0%}</td>'
            f'<td class="num">{t.n_days}</td></tr>')

    notes = ""
    if feats.notes:
        notes = ('<div class="banner"><strong>확인 필요</strong><br>'
                 + "<br>".join(esc(n) for n in feats.notes) + "</div>")

    return f"""<section>
<h2>{esc(kw)}</h2>
<p class="sub">판단 기준 시점 T_cut {esc(t_cut)} · 이 시점 이전 자료만 사용 ·
관측 채널 {feats.channel_count}개 · 전년 동기 대비 {fmt(feats.seasonality_ratio)}</p>
{notes}
<div class="card">
  <h3>채널별 추이</h3>
  {line_chart(chans, t_cut)}
</div>
<div class="card">
  <h3>연령 쏠림 (분야 기준선 대비 리프트)</h3>
  {lift_chart(age)}
  <p class="note">네이버쇼핑은 어느 키워드든 40대가 최다로 나온다. 채널 이용자층이
  그런 것이라 분야 전체 분포를 기준선으로 두고 그 대비로 읽는다.</p>
</div>
<div class="card">
  <h3>수치 요약</h3>
  <div class="scroll"><table><thead><tr>
    <th>채널</th><th>변화율 (최근 7일 / 직전 28일)</th><th>기울기</th>
    <th>커버리지</th><th>관측일</th></tr></thead>
    <tbody>{"".join(rows) or '<tr><td colspan="5">자료 없음</td></tr>'}</tbody>
  </table></div>
</div>
</section>"""


def build(conn) -> str:
    cases = conn.execute("SELECT * FROM trend_case ORDER BY case_id").fetchall()
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    total = conn.execute("SELECT COUNT(*) FROM signal_raw").fetchone()[0]
    chans = conn.execute("SELECT COUNT(DISTINCT channel) FROM signal_raw").fetchone()[0]
    cands = conn.execute("SELECT COUNT(*) FROM signal_candidate").fetchone()[0]

    kpi = "".join(
        f'<div class="kpi"><div class="label">{l}</div><div class="value">{v}</div></div>'
        for l, v in (("케이스", f"{len(cases)}건"), ("수집 레코드", f"{total:,}"),
                     ("채널", f"{chans}개"), ("후보 클러스터", f"{cands}개")))

    body = "".join(case_section(conn, c) for c in cases) or (
        '<section><div class="card"><p class="note">등록된 케이스가 없다. '
        'scripts/build_case.py 로 만든다.</p></div></section>')

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>케이스 분석 · 트렌드 시그널 검증</title>
<style>{webtheme.CSS}</style></head>
<body><div class="wrap">
<h1>케이스 분석</h1>
<p class="sub">역추적 케이스별로 T_cut 시점에 무엇이 관측됐는지</p>
{webtheme.nav("cases.html")}
<p class="note">생성 {esc(now)}</p>
<div class="kpis">{kpi}</div>
{body}
<footer>
판정(확정·보류·기각)은 검증 파트의 몫이다. 이 화면은 관측된 사실만 보여준다.<br>
모든 수치는 T_cut 이전 자료만으로 계산했다. 정답 라벨은 이 화면에 나오지 않는다.<br>
<a href="https://github.com/CalainKim/Trend_Verification_System">저장소</a>
</footer>
</div><div id="tip" role="status"></div>
<script>{webtheme.TOOLTIP_JS}</script></body></html>
"""


def main() -> int:
    conn = storage.connect()
    storage.init_db(conn)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(conn), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} 생성 ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
