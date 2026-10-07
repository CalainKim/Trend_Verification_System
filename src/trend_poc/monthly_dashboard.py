"""Compact, script-free presentation of saved monthly PoC records."""
from .monthly_report import (
    _badge, _comparison, _comparison_csv, _details, _download, _esc,
    _finite, _first_sentence, _json, _missing_note, _monthly_csv,
    _monthly_details, _num, _pct, _reasons, _reference, _series, monthly_chart,
)


CSS = """*{box-sizing:border-box}
body{margin:0;background:#f4f5f7;color:#19222f;font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif}
a{color:#2458bf;text-underline-offset:3px}
h1,h2,h3,h4,p{margin:0}
main{max-width:1180px;margin:auto;padding:28px 32px 40px}
h1{font-size:30px;letter-spacing:-1px;line-height:1.3}
h2{font-size:26px;letter-spacing:-.8px}
h3{font-size:17px;letter-spacing:-.3px}
h4{font-size:14px}
small,.muted{color:#5d6675}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}
.eyebrow{font-size:12px;font-weight:750;color:#416496;margin-bottom:5px;letter-spacing:.7px}
.scope{font-size:13px;color:#596477;margin-top:7px}
.status{font-size:12px;text-align:right;color:#596477;white-space:nowrap}
.status b{color:#19222f}
.status-dot{display:inline-block;width:7px;height:7px;background:#276752;border-radius:50%;margin-right:6px}
.picker{border:0;padding:0;margin:0;min-width:0}
.picker legend{font-size:13px;color:#5d6675;margin-bottom:10px}
.case-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:20px}
.option{position:relative;cursor:pointer;border:1px solid #ccd2db;border-radius:10px;background:white;padding:17px 20px;display:flex;flex-direction:column;gap:5px;transition:border-color .15s,background .15s;min-width:0}
.option:hover{border-color:#315fbd}
.option-name{font-size:17px;font-weight:750;display:flex;justify-content:space-between;align-items:center}
.option-name:after{content:'↗';font-size:16px;color:#6d7789}
.option-metric{font-size:33px;letter-spacing:-1.3px;line-height:1.3;font-weight:760;font-variant-numeric:tabular-nums}
.option-note{font-size:12px;color:#596477}
.option-status{font-size:12px;color:#364359;margin-top:4px;border-top:1px solid #e5e8ee;padding-top:8px}
.case-toggle{position:absolute;opacity:0;width:1px;height:1px}
.case-toggle:focus-visible~.case-options{outline:3px solid #85aaff;outline-offset:4px}
.panels>.case-card{display:none}
.case-card{background:white;border:1px solid #d5dbe3;border-radius:12px;overflow:hidden;min-width:0}
.case-head{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:23px 26px;border-bottom:1px solid #e3e7ed}
.definition{font-size:13px;color:#5d6675;margin-top:3px}
.head-metric{text-align:right;flex-shrink:0;font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
.head-metric small{display:block;font-size:12px;font-weight:400}
.badge{display:inline-flex;align-items:center;font-size:12px;line-height:1.5;font-weight:700;border-radius:5px;padding:4px 8px;white-space:nowrap}
.watch{background:#e3f2eb;color:#176043}
.hold{background:#fff0d7;color:#80531a}
.neutral{background:#edf0f4;color:#475568}
.workspace{display:block}
.block{padding:23px 26px;min-width:0}
.block-label{font-size:12px;color:#5b6678;margin-bottom:6px}
.metric-note{font-size:12px;color:#636d7a;margin-top:15px}
.review-state{display:flex;justify-content:space-between;gap:12px;align-items:center}
.review-summary{font-size:17px;line-height:1.65;letter-spacing:-.3px;font-weight:650;margin:14px 0 17px}
.reasons{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.reason{border-left:3px solid #2c8263;padding-left:12px}
.reason.counter{border-color:#b57c37}
.reason h4{color:#24634e;margin-bottom:5px}
.reason.counter h4{color:#835b27}
.reason ul{margin:0;padding-left:17px;font-size:14px;line-height:1.7;color:#354052}
.reason li+li{margin-top:4px}
.unrun{font-size:15px;padding:16px;background:#fff6e8;border:1px solid #edddc3;border-radius:7px;margin-top:16px}
.empty{font-size:13px;color:#606c7c}
.result-block{border-top:1px solid #e3e7ed;background:#fafbfc}
.result-top{display:flex;justify-content:space-between;align-items:center;gap:12px}
.comparison-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:17px 0 0}
.comparison-cell{padding:0 18px;border-left:1px solid #dce2e9;min-width:0}
.comparison-cell:first-child{padding-left:0;border:0}
.comparison-cell small{font-size:12px;display:block;margin-bottom:7px}
.comparison-cell strong{font-size:15px}
.result-note{font-size:13px;color:#5d6877;margin-top:15px}
.followup-chart{max-width:670px;margin:18px auto 0}
.monthly-chart{display:block;width:100%;height:auto;max-height:500px}
.monthly-chart text{font-family:system-ui,"Malgun Gothic",sans-serif}
.chart-label{font-size:11px;font-weight:700}
.axis-label{font-size:9px;fill:#536277}
.cut-label{font-size:9px;fill:#526888}
.peak-label{font-size:9px;fill:#2456a5;font-weight:700}
.chart-note{font-size:12px;color:#5d6877;margin-top:8px}
.missing{font-size:13px;color:#815b24}
.resources{padding:0 26px 20px;border-top:1px solid #e3e7ed}
details{margin-top:14px}
summary{font-size:13px;font-weight:600;cursor:pointer;color:#40516a;padding:5px 0}
summary:hover{color:#2458bf}
a:focus-visible,summary:focus-visible{outline:3px solid #85aaff;outline-offset:4px}
.sources-grid{display:grid;gap:14px;padding:7px 0}
.source{border-left:2px solid #bdc9dc;padding-left:12px}
.source-title{font-size:14px;font-weight:650}
.source p{font-size:13px;color:#49566a;margin-top:7px}
.source small{display:block;margin-top:7px;font-size:12px}
.source-title a{text-decoration:none}
.source-title a:hover{text-decoration:underline}
.comparison{margin:10px 0;display:grid;gap:12px}
.comparison dt{font-size:12px;color:#5d6877}
.comparison dd{margin:0;font-size:14px}
.contribution,.assessment{font-size:13px;margin-top:8px}
.case-links,.footer-links{display:flex;gap:16px;flex-wrap:wrap}
.case-links{margin-top:16px}
.case-links a,.footer-links a{font-size:12px;text-decoration:none}
.case-links a:hover,.footer-links a:hover{text-decoration:underline}
pre{font:12px/1.65 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:350px;overflow:auto;padding:14px;background:#f0f2f6;border-radius:6px}
.monthly-table-wrap{overflow-x:auto}
.monthly-table{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}
.monthly-table caption{text-align:left;color:#5d6877;font-size:12px;margin-bottom:8px}
.monthly-table th,.monthly-table td{text-align:right;padding:8px;border-bottom:1px solid #dde2ea;white-space:nowrap}
.monthly-table th:first-child{text-align:left}
.footer{display:flex;justify-content:space-between;gap:16px;margin-top:20px;font-size:12px;color:#5d6877}
.method{margin-top:14px}
.method p{font-size:13px;color:#5d6877;margin-top:6px}
.single .case-card{display:block}
.single .topbar{margin-bottom:18px}
@media(max-width:760px){main{padding:20px 18px 30px}
.topbar{align-items:flex-start;margin-bottom:20px}
h1{font-size:26px}
.status{font-size:11px}
.case-options{gap:8px}
.option{padding:12px}
.option-name{font-size:16px}
.option-metric{font-size:27px}
.option-note,.option-status{font-size:11px}
.workspace{grid-template-columns:1fr}
.block{padding:20px}
.case-head{padding:20px}
.resources{padding:0 20px 18px}
.review-summary{font-size:16px}
.reasons{grid-template-columns:1fr 1fr;gap:20px}
.footer{flex-direction:column;gap:10px}
.head-metric{font-size:18px}
.comparison-cell{padding:0 10px}
.comparison-cell strong{font-size:14px}
}
@media(max-width:440px){main{padding:18px 12px 28px}
.status{display:none}
.option{padding:10px 9px}
.option-name{font-size:15px}
.option-name:after{display:none}
.option-metric{font-size:23px}
.option-note{font-size:10px}
.case-options{gap:6px}
.case-head{padding:17px;gap:10px}
.head-metric{display:none}
.block{padding:18px 17px}
.reasons{grid-template-columns:1fr;gap:16px}
.review-summary{font-size:16px}
.comparison-cell{padding:0 8px}
.comparison-cell strong{font-size:12px}
.comparison-cell small{font-size:11px}
.resources{padding:0 17px 17px}
.result-top{align-items:flex-start}
.result-top h3{font-size:16px}
.missing{font-size:12px}
.option-status{font-size:10px}
}
@media print{body{background:white}
main{max-width:none;padding:0}
.case-options,.case-toggle,.footer-links,.case-links,.method{display:none}
.panels>.case-card{display:block!important;break-before:page;border:0}
.panels>.case-card:first-child{break-before:auto}
.workspace{grid-template-columns:1fr 1fr}
.block{break-inside:avoid}
.resources{display:none}
.topbar{margin-bottom:15px}
}

"""


def _case_card(case, year, index, single=False, report=None):
    selection, review, outcome = (case.get(k) or {} for k in ("selection", "review", "outcome"))
    result = review.get("result") or {}
    actual = review.get("status") == "complete" and bool(result)
    series = _series(case, year)
    has_series = any(row.get(k) is not None for row in series.values() for k in ("shopping", "search"))
    pending = outcome.get("label") == "후속 자료 미수집"
    bits = [f'<article class="case-card" id="case-{index}" aria-labelledby="case-title-{index}">',
            '<header class="case-head"><div>',
            f'<h2 id="case-title-{index}">{_esc(case.get("keyword"))}</h2><p class="definition">{_esc(_first_sentence(case.get("definition")))}</p></div>',
            f'<div class="head-metric">{_pct(selection.get("growth_pct"))}<small>4월 쇼핑 · 전월 대비</small></div></header>',
            '<div class="workspace"><section class="block review-block"><div class="block-label">01 · 선정 근거 — 3~4월 자료로 본 판단</div><div class="review-state"><h3>모델은 왜 이렇게 판단했나</h3>',
            _badge(result.get("verdict")) if actual else _badge(review.get("status") or "미실행"), '</div>']
    if actual:
        # Never truncate a sentence that may contain a qualification or negation.
        bits += [f'<p class="review-summary">{_esc(result.get("display_summary") or result.get("summary") or "")}</p>',
                 '<div class="reasons"><div class="reason"><h4>지지 이유</h4>', _reasons(result.get("support")),
                 '</div><div class="reason counter"><h4>반대 이유</h4>', _reasons(result.get("against")), '</div></div>']
    else:
        bits.append('<p class="unrun">완료된 모델 응답이 없습니다.</p>')
    bits += ['<p class="metric-note">4월까지의 변화를 보고 내린 판단입니다. 4월 상승을 미리 예측한 결과는 아닙니다.</p>',
             '</section></div><section class="block result-block"><div class="result-top"><h3>02 · 이후 결과와 비교</h3>',
             '<span class="missing">5~10월 미조회</span>' if pending else f'<span class="missing">{_esc(_missing_note(case, year))}</span>',
             '</div><div class="comparison-strip"><div class="comparison-cell"><small>수치 기준 판단</small>',
             _badge(selection.get("status")), '</div><div class="comparison-cell"><small>AI 판단</small>',
             _badge(result.get("verdict")) if actual else '<strong>미완료</strong>',
             '</div><div class="comparison-cell"><small>실제 확산 여부</small>',
             f'<strong>{"확인 전" if pending else _esc(outcome.get("label") or "미확인")}</strong></div></div>']
    if has_series:
        bits += ['<div class="followup-chart">', monthly_chart(case, year), '</div>',
                 f'<p class="result-note">{_esc(outcome.get("summary") or "")}</p>']
    elif not pending:
        bits.append('<p class="result-note">월별 자료 부족 · 결과 비교 불가</p>')
    if pending:
        bits.append('<p class="result-note">후속 자료가 연결되면 월별 흐름과 설명의 도움 여부를 비교합니다.</p>')
    else:
        bits += ['<details><summary>AI 설명과 이후 사실 비교</summary>', _comparison(case), '</details>']
    refs = [ref for ref in outcome.get("references") or [] if isinstance(ref, dict)]
    bits += ['</section><section class="resources">',
             f'<details><summary>확인 자료 · 외부 기록 {len(refs)}건</summary><div class="sources-grid">',
             *[_reference(ref) for ref in refs], '</div></details>',
             '<details><summary>수치·원문·실행 기록</summary>',
             _monthly_details(case, year) if has_series else '',
             _details("정의·선정 수치", {"definition": case.get("definition"), "selection": selection,
                 "note": "선정 수치는 3~4월 요청, 그래프는 3~10월 요청. 서로 다른 요청의 지수 크기는 직접 비교하지 않습니다."}),
             _details("모델 응답 원문과 미확인 사항", review),
             _details("출처·조건·실행 기록", case.get("provenance") or {}),
             _details("사례 전체 데이터", case), '</details><div class="case-links">']
    if not single and report:
        bits.append(_download(render_dashboard(report, index - 1), "text/html;charset=utf-8", f"case-{index:02}.html", "사례 HTML ↓"))
    else:
        bits.append(_download(_json(case), "application/json", f"case-{index:02}.json", "사례 JSON ↓"))
    bits += [_download(_monthly_csv(case, year), "text/csv;charset=utf-8", f"case-{index:02}-metrics.csv", "월별 CSV ↓"),
             '</div></section></article>']
    return ''.join(bits)


def render_dashboard(report, index=None):
    year = int(report.get("year", 2025))
    cases = report.get("cases") or []
    single = index is not None
    title = f'{cases[index].get("keyword")} · 트렌드 후보 검증' if single else '트렌드 후보 검증'
    complete = sum(c.get("review", {}).get("status") == "complete" for c in cases)
    # Start on a usable review without changing the stored order or classifications.
    default = next((i for i, c in enumerate(cases, 1) if c.get("review", {}).get("status") == "complete" and c.get("selection", {}).get("status") == "WATCH"), 1)
    switch_css = ''.join(f'#pick-{i}:checked~.panels>#case-{i}{{display:block}}#pick-{i}:checked~.case-options>label[for="pick-{i}"]{{background:#edf3ff;border-color:#315fd1;box-shadow:inset 0 0 0 1px #315fd1}}#pick-{i}:checked~.case-options>label[for="pick-{i}"] .option-name:after{{content:"●";color:#315fd1;font-size:11px}}' for i in range(1, len(cases)+1))
    bits = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
            f'<title>{_esc(title)}</title><style>{CSS}{switch_css}</style></head><body'+(' class="single"' if single else '')+'><main>',
            f'<header class="topbar"><div><p class="eyebrow">{year} · 패션 관심 지표</p><h1>{_esc(title)}</h1><p class="scope">3~4월 근거 검토 → 관찰 여부와 이유 → 이후 변화 비교</p></div>',
            f'<p class="status"><span class="status-dot"></span>저장된 결과<br><b>AI 검토 {complete}/{len(cases)}</b></p></header>']
    if not single:
        bits.append('<fieldset class="picker"><legend>아이템을 선택해 근거와 판단을 확인하세요</legend>')
        for i, case in enumerate(cases, 1):
            bits.append(f'<input class="case-toggle" type="radio" name="item" id="pick-{i}" aria-label="{_esc(case.get("keyword"))} 검토"'+(' checked' if i == default else '')+'>')
        bits.append('<div class="case-options">')
        for i, case in enumerate(cases, 1):
            selection = case.get("selection") or {}
            label = {"WATCH": "수치 기준 충족", "NOT_SUPPORTED": "수치 기준 미충족", "HOLD": "자료 확인 필요"}.get(selection.get("status"), "미확인")
            bits.append(f'<label class="option" for="pick-{i}"><span class="option-name">{_esc(case.get("keyword"))}</span><span class="option-metric">{_pct(selection.get("growth_pct"))}</span><span class="option-note">4월 쇼핑 · 3월 대비</span><span class="option-status">{label}</span></label>')
        bits.append('</div><div class="panels">')
        bits.extend(_case_card(case, year, i, report=report) for i, case in enumerate(cases, 1))
        bits.append('</div></fieldset>')
    else:
        bits.append(_case_card(cases[index], year, index+1, True, report))
    bits += ['<details class="method"><summary>비교 기준과 해석 범위</summary><p>관찰 기준: 4월 쇼핑 지수가 3월보다 20% 이상 증가. 유행 확정 기준은 아닙니다.</p>',
             f'<p>{_esc(report.get("retrospective_note") or "")}</p><p>상대 관심 지표이며 실제 판매량을 뜻하지 않습니다. 초기 판단에는 3~4월 자료만 사용합니다.</p></details>',
             '<footer class="footer"><span>네이버 월간 지수 · 저장된 응답 기준</span><div class="footer-links">',
             f'<a href="" download="{"index.html" if not single else f"case-{index+1:02}.html"}">보고서 HTML ↓</a>']
    if not single:
        bits += [_download(_json(report), "application/json", "suite.json", "전체 JSON ↓"),
                 _download(_comparison_csv(report), "text/csv;charset=utf-8", "comparison.csv", "비교 CSV ↓")]
    bits.append('</div></footer></main></body></html>')
    return ''.join(bits)
