"""Synthetic offline fixtures verify monthly-report trust and display boundaries."""
import copy
import base64
import csv
import io
import json
import re
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from trend_poc.monthly_report import _axis_max, _document, monthly_chart, write_monthly_exports


def fixture():
    return {"schema_version":"monthly-fixture","year":2025,"generated_at":"2026-10-06T00:00:00+09:00",
            "retrospective_note":"테스트 전용 합성 자료. 실제 실험 결과가 아닙니다.","cases":[{
                "keyword":"테스트 후보","definition":"테스트용 입력",
                "selection":{"status":"WATCH","growth_pct":25,"march":20,"april":25},
                "review":{"status":"complete","model":"test-model","result":{"verdict":"HOLD","summary":"검토 조건을 기록했습니다.",
                    "support":[{"text":"첫 근거","evidence_ids":["s1"]},{"text":"둘째 근거","evidence_ids":["s2"]},{"text":"셋째 원문만","evidence_ids":["s3"]}],
                    "against":[{"text":"확인할 조건","evidence_ids":["a1"]}],"unknowns":["확인되지 않은 것"]}},
                "series":[{"month":f"2025-{m:02}","shopping":20+m if m not in (6,10) else None,"search":40+m if m!=10 else None} for m in range(3,11)],
                "outcome":{"label":"관측 기록","summary":"결측을 남긴 관측입니다.","peak_month":"2025-09","peak_value":29,"missing_months":["2025-10"],
                    "references":[{"id":"period","title":"관측 기간 있는 기록","url":"https://example.org/record","published_at":"2025-07-10","observed_start":"2025-05-01","observed_end":"2025-05-31","population":"전체 이용자","summary":"확인 범위만 서술"},
                                  {"id":"posted","title":"게시일만 있는 기록","url":"https://example.org/posted","published_at":"2025-08-05","observed_start":None,"observed_end":None,"population":"대상 미상","summary":"관측 기간을 추정하지 않음"}]},
                "comparison":{"baseline":"수치 비교","ai":"조건 구분","observed":"월별 관측","contribution":None,"assessment":None,"checks":[]},
                "provenance":{"source":"offline fixture"}}]}


def test_missing_month_breaks_each_channel_without_zero_fill():
    case=fixture()["cases"][0]
    chart=monthly_chart(case,2025)
    assert chart.count('class="series-line shopping"')==2
    assert chart.count('class="series-line search"')==1
    assert chart.count('class="series-point shopping"')==6
    assert "관측 최고" not in chart or 'class="observed-peak"' in chart
    assert 'class="observed-peak"' in chart and "9월 최고 29.0" in chart


def test_external_observation_period_and_publication_are_distinct():
    chart=monthly_chart(fixture()["cases"][0],2025)
    assert chart.count('class="external-observation" data-reference="period"')==2
    assert 'class="external-observation" data-reference="posted"' not in chart
    assert chart.count('class="publication-only" data-reference="posted"')==1
    assert 'class="publication-only" data-reference="period"' not in chart
    page=_document(fixture())
    assert "관측 2025-05-01–2025-05-31" in page
    assert "게시 2025-08-05" in page and "관측 기간 미기록" in page
    assert "대상 전체 이용자" in page


def test_report_does_not_invent_effect_or_force_outcome():
    data=fixture()
    page=_document(data)
    assert "효과 있음" not in page
    assert "기여도에 대한 별도 평가가 기록되지 않았습니다" in page
    assert "10월 자료 부족" in page
    assert "0/4" not in page and "0 / 4" not in page
    assert "트렌드 후보 검증" in page
    data["cases"][0]["review"]["status"]="failed"
    page=_document(data)
    assert "완료된 모델 응답이 없습니다" in page
    assert '<p class="review-summary">' not in page


def test_all_source_and_model_content_is_escaped_and_links_are_safe():
    data=fixture()
    bad='<script>alert("x")</script>'
    case=data["cases"][0]
    case["keyword"]=bad
    case["review"]["result"]["summary"]=bad
    case["outcome"]["references"][0].update(title=bad,url="javascript:alert(1)",population=bad)
    case["outcome"]["references"][1]["url"]="data:text/html,bad"
    page=_document(data)
    assert bad not in page and "&lt;script&gt;" in page
    assert 'href="javascript:' not in page and 'href="data:text/html,bad"' not in page
    # Only renderer-owned, base64 downloads can use data URLs.
    for uri in re.findall(r'href="(data:[^"]+)"',page):
        assert ";base64," in uri
    assert '<script' not in page and '<link ' not in page
    assert 'role="img"' in page and 'aria-label=' in page


def test_exports_preserve_raw_records_and_produce_complete_offline_paths(tmp_path):
    data=fixture()
    data["cases"]=[copy.deepcopy(data["cases"][0]) for _ in range(3)]
    before=copy.deepcopy(data)
    paths=write_monthly_exports(tmp_path,data)
    assert json.loads(paths["json"].read_text(encoding="utf-8"))==before
    assert data==before and len(paths["cases"])==3
    page=paths["html"].read_text(encoding="utf-8")
    for index,case_paths in enumerate(paths["cases"],1):
        assert f'download="case-{index:02}.html"' in page
        assert all(p.is_file() for p in case_paths.values())
        case_page=case_paths["html"].read_text(encoding="utf-8")
        assert f'download="case-{index:02}.json"' in case_page
        rows=list(csv.DictReader(io.StringIO(case_paths["csv"].read_text(encoding="utf-8-sig"))))
        assert len(rows)==8 and rows[3]["shopping"]=="" and rows[-1]["shopping"]==""
    assert paths["csv"].name=="comparison.csv"


def test_portable_downloads_embed_the_exported_bytes():
    data=fixture()
    page=_document(data)
    assert 'href="" download="index.html"' in page
    links=re.findall(r'href="data:([^,]+),([A-Za-z0-9+/=]+)" download="([^"]+)"',page)
    downloads={name:(mime,base64.b64decode(payload).decode("utf-8")) for mime,payload,name in links}
    assert json.loads(downloads["suite.json"][1])==data
    assert list(csv.DictReader(io.StringIO(downloads["comparison.csv"][1])))[0]["keyword"]=="테스트 후보"
    assert '<!doctype html>' in downloads["case-01.html"][1]
    assert 'download="case-01-metrics.csv"' in downloads["case-01.html"][1]


def test_compact_copy_preserves_later_negative_conclusion_and_hides_main_ids():
    data=fixture()
    case=data["cases"][0]
    case["definition"]="간단한 정의입니다. 긴 근거와 자료 해석은 상세에서만 봅니다."
    case["review"]["result"]["summary"]="지표는 상승했습니다. 그러나 이후 지속을 지지하지는 않습니다."
    case["review"]["result"]["support"][0]["display_text"]="관측 상승만 확인됐습니다."
    page=_document(data)
    definition=re.search(r'<p class="definition">(.*?)</p>',page).group(1)
    assert definition=="간단한 정의입니다."
    assert "긴 근거와 자료 해석은 상세에서만 봅니다" in page
    summary=re.search(r'<p class="review-summary">(.*?)</p>',page).group(1)
    assert "그러나 이후 지속을 지지하지는 않습니다" in summary
    main_review=page.split('<section class="block review-block">',1)[1].split('</section>',1)[0]
    assert "관측 상승만 확인됐습니다" in main_review
    assert "<small>s1</small>" not in main_review
    assert "근거: s1" in main_review  # Tooltip retains original traceability.
    assert "test-model" not in main_review
    assert "4월 자료로 본 판단" in main_review and "4월에 받은" not in main_review
    assert "AI 판단" in page and "AI가 덧붙인 점" not in page


def test_channel_axes_fit_actual_raw_values_without_smoothing_or_rescaling(tmp_path):
    data=fixture()
    chart=monthly_chart(data["cases"][0],2025)
    assert _axis_max([0,0])==1
    assert _axis_max([.2,.6])==1
    assert _axis_max([23,29])==30
    assert _axis_max([43,49])==50
    assert '>30</text>' in chart and '>50</text>' in chart
    assert '>100</text>' not in chart
    assert '<path ' not in chart and 'class="series-line shopping"' in chart
    paths=write_monthly_exports(tmp_path,data)
    rows=list(csv.DictReader(io.StringIO(paths["cases"][0]["csv"].read_text(encoding="utf-8-sig"))))
    assert rows[0]["shopping"]=="23" and rows[6]["shopping"]=="29"
    assert json.loads(paths["json"].read_text(encoding="utf-8"))==data


def test_card_hides_initial_raw_values_but_details_and_csv_include_monthly_changes(tmp_path):
    data=fixture()
    case=data["cases"][0]
    case["series"][1].update(shopping_growth_pct=4.347826,search_growth_pct=2.325581)
    page=_document(data)
    head=page.split('<header class="case-head">',1)[1].split('</header>',1)[0]
    assert "+25.0%" in head and "→" not in head
    assert 'class="selection-details"' not in page
    assert "선정 수치는 3~4월 요청, 그래프는 3~10월 요청" in page
    assert '<table class="monthly-table">' in page and '<th scope="col">전월 대비</th>' in page
    assert "+4.3%" in page and "+2.3%" in page
    paths=write_monthly_exports(tmp_path,data)
    rows=list(csv.DictReader(io.StringIO(paths["cases"][0]["csv"].read_text(encoding="utf-8-sig"))))
    assert rows[0]["shopping_growth_pct"]==""
    assert rows[1]["shopping_growth_pct"]=="4.347826"
    assert rows[1]["search_growth_pct"]=="2.325581"


def test_pending_followup_shows_model_reasons_first_without_empty_future_chart():
    data=fixture()
    case=data["cases"][0]
    case["series"]=[{"month":f"2025-{m:02}","shopping":None,"search":None} for m in range(3,11)]
    case["outcome"]["label"]="후속 자료 미수집"
    case["provenance"]["bundle"]={"features":{
        "shopping":case["selection"],
        "search":{"march":12,"april":18,"growth_pct":50}}}
    before=copy.deepcopy(data)
    page=_document(data)
    assert 'class="monthly-chart"' not in page
    assert 'class="initial-channel' not in page
    assert '3월보다 얼마나 달라졌나' not in page
    review = page.split('<section class="block review-block">', 1)[1].split('</section>', 1)[0]
    assert '첫 근거' in review and '확인할 조건' in review
    assert '3~4월 자료로 본 판단' in review
    assert '4월 상승을 미리 예측한 결과는 아닙니다' in review
    assert page.index('class="review-summary"') < page.index('02 · 이후 결과와 비교')
    assert '5~10월 미조회' in page
    assert "확인 전" in page
    assert data==before  # No initial/follow-up normalization mixing on export.


def test_missing_model_response_never_uses_numeric_rule_as_model_reason():
    data=fixture()
    data['cases'][0]['review']={'status':'failed'}
    page=_document(data)
    review=page.split('<section class="block review-block">',1)[1].split('</section>',1)[0]
    assert '완료된 모델 응답이 없습니다' in review
    assert 'class="review-summary"' not in review
    assert '첫 근거' not in review


def test_all_model_explanations_remain_available_in_individual_exports(tmp_path):
    data=fixture()
    data["cases"]=[copy.deepcopy(data["cases"][0]) for _ in range(3)]
    for i,case in enumerate(data["cases"],1):
        case["keyword"]=f"후보 {i}"
        case["review"]["result"]["summary"]=f"후보 {i}의 판단. 지속 상승은 확인되지 않았습니다."
    paths=write_monthly_exports(tmp_path,data)
    for i,path in enumerate(paths["cases"],1):
        page=path["html"].read_text(encoding="utf-8")
        assert f"후보 {i}의 판단. 지속 상승은 확인되지 않았습니다." in page
        assert 'class="single"' in page
