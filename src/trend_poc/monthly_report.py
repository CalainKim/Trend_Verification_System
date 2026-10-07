"""Offline monthly case comparison with auditable model and source records."""
from __future__ import annotations

import csv
import base64
from datetime import date, timedelta
import html
import io
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


def _esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _short(value, limit=150):
    value = re.sub(r"\s+", " ", _text(value)).strip()
    return value if len(value) <= limit else value[:limit].rstrip() + "…"


def _first_sentence(value):
    return re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", _text(value)).strip(), maxsplit=1)[0]


def _download(value, mime, filename, label):
    encoded=base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f'<a href="data:{mime};base64,{encoded}" download="{_esc(filename)}">{_esc(label)}</a>'


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _num(value, digits=1):
    return f"{value:,.{digits}f}" if _finite(value) else "—"


def _pct(value):
    return f"{value:+.1f}%" if _finite(value) else "—"


def _axis_max(values):
    maximum=max([1.0]+values)
    if maximum<=1:
        return 1.0
    step=5 if maximum<=50 else 10
    return float(math.ceil(maximum/step)*step)


def _axis_tick(value):
    return _num(value,0 if float(value).is_integer() else 1)


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str)


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _month(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        return None
    return _date(value + "-01")


def _safe_url(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def _badge(status):
    labels = {"WATCH": ("관찰 후보", "watch"), "HOLD": ("보류", "hold"),
              "NOT_SUPPORTED": ("지지 어려움", "neutral"), "complete": ("응답 완료", "watch"),
              "failed": ("실행 실패", "hold"), "running": ("실행 중", "neutral")}
    label, tone = labels.get(status, (status or "미기록", "neutral"))
    return f'<span class="badge {tone}">{_esc(label)}</span>'


def _details(title, value):
    return f'<details><summary>{_esc(title)}</summary><pre>{_esc(_json(value))}</pre></details>'


def _series(case, year):
    """Exclude ambiguous duplicate months, and preserve null values as gaps."""
    rows, duplicate = {}, set()
    for row in case.get("series") or []:
        if not isinstance(row, dict):
            continue
        month = _month(row.get("month"))
        if not month or month.year != year or not 3 <= month.month <= 10:
            continue
        if month.month in rows:
            duplicate.add(month.month)
        rows[month.month] = {key: row.get(key) if _finite(row.get(key)) else None
                            for key in ("shopping", "search", "shopping_growth_pct", "search_growth_pct")}
    for month in duplicate:
        rows.pop(month, None)
    return rows


def _external_marks(references, start, end, x, top, height, publication_y, publications=True):
    """Observation intervals are bands; publication timestamps alone are dots."""
    result = []
    for reference in references:
        if not isinstance(reference, dict):
            continue
        first, last = _date(reference.get("observed_start")), _date(reference.get("observed_end"))
        title, ref_id = reference.get("title") or "외부 기록", reference.get("id") or ""
        if first and last and first <= last:
            a, b = max(first, start), min(last + timedelta(days=1), end)
            if a < b:
                label = f'{title} · 기록이 관측한 기간 {first}–{last}'
                result.append(f'<rect class="external-observation" data-reference="{_esc(ref_id)}" x="{x(a):.2f}" y="{top}" width="{max(x(b)-x(a),1):.2f}" height="{height}" fill="#eebf65" fill-opacity=".14"><title>{_esc(label)}</title></rect>')
        elif publications:
            published = _date(reference.get("published_at"))
            if published and start <= published < end:
                label = f'{title} · 게시일 {published}, 관측 기간 미확인'
                result.append(f'<circle class="publication-only" data-reference="{_esc(ref_id)}" cx="{x(published):.2f}" cy="{publication_y}" r="3.8" fill="#bd8637" stroke="white" stroke-width="1.2"><title>{_esc(label)}</title></circle>')
    return ''.join(result)


def monthly_chart(case, year):
    """Two separate channel panels. A missing month always breaks its line."""
    year = int(year)
    series = _series(case, year)
    references = (case.get("outcome") or {}).get("references") or []
    start, end = date(year,3,1), date(year,11,1)
    width, height, left, right = 360, 314, 33, 17
    x = lambda d: left + ((d - start).days / (end - start).days) * (width-left-right)
    centers = {}
    for month in range(3,11):
        a, b = date(year,month,1), date(year,month+1,1)
        centers[month] = x(a + timedelta(days=(b-a).days/2))
    keyword = case.get("keyword") or "후보"
    bits = [f'<svg class="monthly-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(keyword)}: {year}년 3월부터 10월까지 쇼핑과 검색의 월별 상대 지수. 결측월은 선을 끊고 외부 관측 기간과 게시일을 구분합니다.">',
            '<title>항목별 축. 선정 수치는 3~4월 요청, 그래프는 3~10월 요청. 서로 다른 요청의 지수 크기는 직접 비교하지 않습니다.</title>']
    panels = (("shopping", "쇼핑 클릭", "#2867c7", 35), ("search", "검색 · 보조", "#398a81", 168))
    for key,label,color,top in panels:
        ph = 76
        values = [row[key] for row in series.values() if row[key] is not None]
        maximum = _axis_max(values)
        y = lambda value: top + ph * (1-value/maximum)
        bits.append(f'<text x="{left}" y="{top-13}" class="chart-label" fill="{color}">{label}</text>')
        bits.append(f'<rect x="{x(date(year,4,1)):.2f}" y="{top}" width="{x(date(year,5,1))-x(date(year,4,1)):.2f}" height="{ph}" fill="#2867c7" fill-opacity=".045"/>')
        bits.append(_external_marks(references,start,end,x,top,ph,285,publications=key=="shopping"))
        for value in (0,maximum/2,maximum):
            yy = y(value)
            bits += [f'<line x1="{left}" x2="{width-right}" y1="{yy:.2f}" y2="{yy:.2f}" stroke="#e2e8f0" stroke-width=".8"/>',
                     f'<text x="{left-7}" y="{yy+3:.2f}" text-anchor="end" class="axis-label">{_axis_tick(value)}</text>']
        cut = x(date(year,5,1))
        bits.append(f'<line class="april-marker" x1="{cut:.2f}" x2="{cut:.2f}" y1="{top}" y2="{top+ph}" stroke="#8398b6" stroke-width="1" stroke-dasharray="3 3"/>')
        segments, segment = [], []
        for month in range(3,11):
            value = (series.get(month) or {}).get(key)
            if value is None:
                if segment:
                    segments.append(segment)
                    segment=[]
                continue
            segment.append((month,value))
        if segment:
            segments.append(segment)
        for segment in segments:
            if len(segment)>1:
                points=' '.join(f'{centers[m]:.2f},{y(v):.2f}' for m,v in segment)
                bits.append(f'<polyline class="series-line {key}" points="{points}" fill="none" stroke="{color}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>')
            for month,value in segment:
                bits.append(f'<circle class="series-point {key}" cx="{centers[month]:.2f}" cy="{y(value):.2f}" r="2.8" fill="{color}" stroke="white" stroke-width="1"><title>{month}월 {label} {_num(value)}</title></circle>')
        if key=="shopping":
            peak = _month((case.get("outcome") or {}).get("peak_month"))
            if peak and peak.year==year and peak.month in centers:
                value=(series.get(peak.month) or {}).get(key)
                if value is not None:
                    xx,yy=centers[peak.month],y(value)
                    anchor="end" if peak.month>=8 else "start"
                    tx=xx-5 if anchor=="end" else xx+5
                    bits += [f'<circle class="observed-peak" cx="{xx:.2f}" cy="{yy:.2f}" r="5" fill="white" stroke="{color}" stroke-width="2"/>',
                             f'<text x="{tx:.2f}" y="{max(top+12,yy-9):.2f}" text-anchor="{anchor}" class="peak-label">{peak.month}월 최고 {_num(value)}</text>']
        if not values:
            bits.append(f'<text x="{(left+width-right)/2:.1f}" y="{top+ph/2:.1f}" text-anchor="middle" class="axis-label">자료 없음</text>')
    bits.append(f'<text x="{x(date(year,5,1))+4:.2f}" y="135" class="cut-label">4월 검토 경계</text>')
    for month in range(3,11):
        bits.append(f'<text x="{centers[month]:.2f}" y="263" text-anchor="middle" class="axis-label">{month}월</text>')
    # Publication dots are on their own source timeline, not on the metric line.
    bits.append('<text x="33" y="306" class="axis-label">음영: 외부 기록의 관측 기간 · 점: 게시일만 확인</text>')
    bits.append('</svg>')
    return ''.join(bits)


def _missing_note(case, year):
    if (case.get("outcome") or {}).get("label") == "후속 자료 미수집":
        return "월별 자료 조회 전"
    missing = (case.get("outcome") or {}).get("missing_months") or []
    months = []
    for value in missing:
        parsed = _month(value)
        if parsed and parsed.year==int(year):
            months.append(parsed.month)
        elif isinstance(value, int) and not isinstance(value,bool) and 1<=value<=12:
            months.append(value)
        elif isinstance(value,str) and re.fullmatch(r"(?:[1-9]|1[0-2])월",value):
            months.append(int(value[:-1]))
    if not months:
        series=_series(case,int(year))
        months=[m for m in range(3,11) if (series.get(m) or {}).get("shopping") is None]
    if not months:
        return ""
    return '·'.join(str(m) for m in sorted(set(months))) + "월 자료 부족"


def _reasons(items):
    values=[]
    for item in (items or [])[:2]:
        if isinstance(item,dict):
            text=item.get("display_text") or item.get("compact_text") or item.get("text") or item.get("claim") or ""
            original=item.get("text") or item.get("claim") or text
            ids=item.get("evidence_ids") or []
        else:
            text,original,ids=item,item,[]
        # Compact copy is supplied by the caller; never cut a later negation off
        # the model's explanation just to make it fit a fixed-height card.
        tooltip=_text(original)+(f' · 근거: {" · ".join(map(str,ids))}' if ids else '')
        values.append(f'<li title="{_esc(tooltip)}">{_esc(_text(text))}</li>')
    return '<ul>'+''.join(values)+'</ul>' if values else '<p class="empty">작성된 항목 없음</p>'


def _reference(reference):
    title=reference.get("title") or "외부 기록"
    url=_safe_url(reference.get("url"))
    heading=f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{_esc(title)} ↗</a>' if url else _esc(title)
    first,last=_date(reference.get("observed_start")),_date(reference.get("observed_end"))
    if first and last and first<=last:
        timing=f"관측 {first}–{last}"
    else:
        timing="관측 기간 미기록"
    published=_date(reference.get("published_at"))
    publication=f"게시 {published}" if published else "게시일 미기록"
    population=reference.get("population") or "대상 집단 미기록"
    return (f'<article class="source"><div class="source-title">{heading}</div>'
            f'<p>{_esc(_short(reference.get("summary"),190))}</p>'
            f'<small>{_esc(timing)}<br>{_esc(publication)} · 대상 {_esc(population)}</small></article>')


def _comparison(case):
    value=case.get("comparison") or {}
    labels=(("baseline","수치만 봤을 때"),("ai","AI 판단"),("observed","이후 관측"))
    rows=''.join(f'<div><dt>{label}</dt><dd>{_esc(_short(value.get(key),170)) or "미기록"}</dd></div>' for key,label in labels)
    assessment=_short(value.get("assessment"),200)
    contribution=_short(value.get("contribution"),200)
    extras=''
    if contribution:
        extras+=f'<p class="contribution">{_esc(contribution)}</p>'
    if assessment:
        extras+=f'<p class="assessment">{_esc(assessment)}</p>'
    if not contribution and not assessment:
        extras+='<p class="empty">기여도에 대한 별도 평가가 기록되지 않았습니다.</p>'
    return '<dl class="comparison">'+rows+'</dl>'+extras


def _monthly_details(case, year):
    values=_series(case,int(year))
    rows=[]
    for month in range(3,11):
        row=values.get(month) or {}
        rows.append(f'<tr><th scope="row">{month}월</th><td>{_num(row.get("shopping"))}</td>'
                    f'<td>{_pct(row.get("shopping_growth_pct"))}</td><td>{_num(row.get("search"))}</td>'
                    f'<td>{_pct(row.get("search_growth_pct"))}</td></tr>')
    return ('<details><summary>월별 수치와 변화율</summary><div class="monthly-table-wrap"><table class="monthly-table">'
            '<caption>3~10월 동일 요청에서 받은 월별 상대 지수와 전월 대비 변화율</caption>'
            '<thead><tr><th scope="col">월</th><th scope="col">쇼핑</th><th scope="col">전월 대비</th>'
            '<th scope="col">검색</th><th scope="col">전월 대비</th></tr></thead><tbody>' + ''.join(rows) +
            '</tbody></table></div><p class="chart-note">선정 수치는 3~4월 요청, 그래프는 3~10월 요청. 서로 다른 요청의 지수 크기는 직접 비교하지 않습니다. 전월이 없거나 0이면 변화율을 표시하지 않습니다.</p></details>')


def _document(report, index=None):
    from .monthly_dashboard import render_dashboard
    return render_dashboard(report, index)


def _csv_cell(value):
    text=_text(value)
    # Preserve numeric values; neutralize formula-like untrusted text on export.
    if isinstance(value,str) and text.lstrip().startswith(("=","+","-","@")):
        return "'"+text
    return text


def _monthly_csv(case,year):
    stream=io.StringIO(newline="")
    writer=csv.writer(stream)
    writer.writerow(["month","shopping","shopping_growth_pct","search","search_growth_pct"])
    series=_series(case,int(year))
    for month in range(3,11):
        value=series.get(month) or {}
        writer.writerow([f"{year}-{month:02}",value.get("shopping"),value.get("shopping_growth_pct"),value.get("search"),value.get("search_growth_pct")])
    return stream.getvalue()


def _comparison_csv(report):
    stream=io.StringIO(newline="")
    writer=csv.writer(stream)
    writer.writerow(["keyword","definition","selection_status","selection_growth_pct","review_status","model_verdict","model","observed_label","peak_month","missing_months","baseline","ai","observed","contribution","assessment"])
    for case in report.get("cases") or []:
        selection,review,outcome,comparison=(case.get(k) or {} for k in ("selection","review","outcome","comparison"))
        result=review.get("result") or {}
        actual=review.get("status")=="complete" and bool(result)
        values=[case.get("keyword"),case.get("definition"),selection.get("status"),selection.get("growth_pct"),review.get("status"),
                result.get("verdict") if actual else None,review.get("actual_model") or review.get("model"),outcome.get("label"),
                outcome.get("peak_month"),outcome.get("missing_months"),*(comparison.get(k) for k in ("baseline","ai","observed","contribution","assessment"))]
        writer.writerow([_csv_cell(v) for v in values])
    return stream.getvalue()


def write_monthly_exports(run_dir: Path, report: dict) -> dict:
    """Write portable report files without fetching data or making model calls."""
    root=Path(run_dir).resolve()
    root.mkdir(parents=True,exist_ok=True)
    paths={"html":root/"index.html","json":root/"suite.json","csv":root/"comparison.csv","cases":[]}
    paths["html"].write_text(_document(report),encoding="utf-8")
    paths["json"].write_text(_json(report)+"\n",encoding="utf-8")
    paths["csv"].write_text(_comparison_csv(report),encoding="utf-8-sig",newline="")
    for index,case in enumerate(report.get("cases") or []):
        folder=root/"cases"/f"{index+1:02}"
        folder.mkdir(parents=True,exist_ok=True)
        saved={"html":folder/"report.html","json":folder/"result.json","csv":folder/"metrics.csv"}
        saved["html"].write_text(_document(report,index),encoding="utf-8")
        saved["json"].write_text(_json(case)+"\n",encoding="utf-8")
        saved["csv"].write_text(_monthly_csv(case,report.get("year",2025)),encoding="utf-8-sig",newline="")
        paths["cases"].append(saved)
    return paths
