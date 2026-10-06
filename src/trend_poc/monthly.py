"""Calendar-month case study. Frozen initial evidence never contains outcomes."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .naver import NaverClient, URLS, _validate_response
from .review import build_payload, digest, now, run_review, save

POLICY = "monthly-followup-v1"
NOTE = "2025년 자료를 현재 조회한 과거 사례 검토입니다. 세 사례로 예측 정확도나 리즈닝의 일반적 우수성을 평가하지 않습니다."
VERDICTS = {"WATCH": "관찰 후보", "NOT_SUPPORTED": "관찰 기준 미충족", "HOLD": "판단 보류"}


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def validate_manifest(manifest):
    if manifest.get("year") != 2025 or len(manifest.get("cases", [])) != 3:
        raise ValueError("이번 사례는 2025년, 서로 다른 스타일 세 개로 고정합니다.")
    keywords = [c["keyword"] for c in manifest["cases"]]
    if len(set(keywords)) != 3 or any(not isinstance(k, str) or not k.strip() for k in keywords):
        raise ValueError("비어 있거나 중복된 후보입니다.")
    ids = set()
    for case in manifest["cases"]:
        if not case.get("definition"):
            raise ValueError("각 키워드의 포함·제외 범위가 필요합니다.")
        for ref in case.get("references", []):
            if not ref.get("id") or ref["id"] in ids:
                raise ValueError("출처 ID는 전체 사례에서 고유해야 합니다.")
            ids.add(ref["id"])
            if urlsplit(ref["url"]).scheme not in ("https", "http") or not urlsplit(ref["url"]).netloc:
                raise ValueError("출처는 HTTP(S) 주소여야 합니다.")
            published = date.fromisoformat(ref["published_at"])
            start, end = ref.get("observed_start"), ref.get("observed_end")
            if bool(start) != bool(end):
                raise ValueError("관측 기간은 시작일과 종료일이 함께 있어야 합니다.")
            if start and not date.fromisoformat(start) <= date.fromisoformat(end) <= published:
                raise ValueError("관측 기간과 게시일 순서를 확인하세요.")
            if not all(ref.get(k) for k in ("title", "summary", "population", "kind")):
                raise ValueError("출처의 제목·내용·고객군·자료 종류가 필요합니다.")
    return manifest


def validate_record(record, channel, keywords, end):
    """Reject altered bytes, changed populations, periods and normalization scopes."""
    payload = record["payload"]
    if (record.get("status") != "complete" or record.get("channel") != channel
            or record.get("provider") not in URLS
            or record.get("url") != URLS[record["provider"]][channel]
            or record.get("request_sha256") != digest({"url": record["url"], "payload": payload})
            or record.get("response_sha256") != digest(record["response"])
            or record.get("record_sha256") != digest({k: v for k, v in record.items() if k != "record_sha256"})):
        raise ValueError("월별 원자료의 해시·출처가 일치하지 않습니다.")
    if (payload.get("startDate") != "2025-03-01" or payload.get("endDate") != end
            or payload.get("timeUnit") != "month" or payload.get("gender") != "m"
            or payload.get("ages") != (["20"] if channel == "shopping" else ["3", "4"])
            or payload.get("device") not in (None, "")
            or (channel == "shopping" and payload.get("category") != "50000169")):
        raise ValueError("기간·월간 집계·고객군·분야 조건이 다릅니다.")
    groups = ([{"name": k, "param": [k]} for k in keywords] if channel == "shopping"
              else [{"groupName": k, "keywords": [k]} for k in keywords])
    if payload.get("keyword" if channel == "shopping" else "keywordGroups") != groups:
        raise ValueError("키워드 또는 묶음이 달라졌습니다.")
    if _validate_response(channel, payload, record["response"]) != record["missing_dates"]:
        raise ValueError("누락 월 기록이 응답과 다릅니다.")
    return record


def points(record, keyword):
    row = next(r for r in record["response"]["results"] if r["title"] == keyword)
    return {p["period"][:7]: p["ratio"] for p in row["data"]}


def signal(values):
    march, april = values.get("2025-03"), values.get("2025-04")
    growth = None
    status = "HOLD"
    if march is not None and april is not None and march > 0:
        base, recent = Decimal(str(march)), Decimal(str(april))
        growth = float((recent / base - 1) * 100)
        status = "WATCH" if recent >= base * Decimal("1.2") else "NOT_SUPPORTED"
    return {"status": status, "march": march, "april": april, "growth_pct": growth}


def build_monthly_bundle(case, records):
    evidence, features = [], {}
    for channel in ("shopping", "search"):
        r = records[channel]
        values = points(r, case["keyword"])
        if any(month not in ("2025-03", "2025-04") for month in values):
            raise ValueError("초기 판단에 5월 이후 자료를 넣을 수 없습니다.")
        features[channel] = signal(values)
        evidence.extend([
            {"id": f"{channel}_request", "request_id": r["id"], "conditions": deepcopy(r["payload"]),
             "population": "네이버 분류 20~29세 남성" if channel == "shopping" else "네이버 분류 19~29세 남성",
             "measure": "월간 쇼핑 클릭 상대 지수" if channel == "shopping" else "월간 검색 상대 지수"},
            {"id": f"{channel}_series", "request_id": r["id"], "points": values},
            {"id": f"{channel}_features", "data": features[channel]},
        ])
    # Future source titles, expected case classes and the source manifest never enter here.
    return {"candidate": {"keyword": case["keyword"], "definition": case["definition"]},
            "claim": "2025년 4월까지 자료로 볼 때 이 아이템을 이후 확산 가능성이 있는 후보로 계속 관찰할 가치가 있는가?",
            "simulated_cutoff": "2025-05-01", "experiment_type": "monthly-retrospective-v1",
            "historical_available_at": None, "features": features, "evidence": evidence,
            "limitations": ["현재 조회한 2025년 자료이며 당시 버전의 가용 시점은 확인하지 못함.",
                            "월간 관측 두 개로 지속 추세나 계절성 원인을 확정할 수 없음.",
                            "쇼핑은 20~29세 남성, 검색은 19~29세 남성. 네이버 두 지표는 완전히 독립적이지 않음.",
                            "같은 요청의 3월 대비 4월 20% 증가를 관찰 기준으로 사용. 실제 구매·유행의 확정 기준이 아님.",
                            "광고·판매량·실제 착용·전년 동월 자료 없음. 모델의 과거 학습 지식은 검증 근거로 쓰지 않음."]}


def monthly_outcome(case, records):
    values = {ch: points(records[ch], case["keyword"]) for ch in ("shopping", "search")}
    series = [{"month": f"2025-{month:02}", **{ch: values[ch].get(f"2025-{month:02}") for ch in values}}
              for month in range(3, 11)]
    for i, row in enumerate(series):
        for ch in ("shopping", "search"):
            previous = series[i - 1][ch] if i else None
            row[ch + "_growth_pct"] = (float((Decimal(str(row[ch])) / Decimal(str(previous)) - 1) * 100)
                                      if row[ch] is not None and previous is not None and previous > 0 else None)
    available = [row for row in series if row["shopping"] is not None]
    peak = max(available, key=lambda row: row["shopping"]) if available else None
    missing = [row["month"] for row in series if row["shopping"] is None]
    april = values["shopping"].get("2025-04")
    followup = [row for row in available if row["month"] >= "2025-05"]
    refs = deepcopy(case.get("references", []))
    # Editorial forecasts and articles about April are not later measured diffusion.
    measured = [r for r in refs if r["kind"] == "measured" and r.get("observed_start")
                and r["observed_start"] >= "2025-05-01" and r["observed_end"] <= "2025-10-31"]
    if not followup:
        label, summary = "후속 자료 부족", "5~10월 쇼핑 지수가 없어 이후 흐름을 판단할 수 없습니다."
    elif missing:
        label = "일부 기간 미확인"
        summary = "·".join(str(int(m[5:])) + "월" for m in missing) + " 쇼핑 자료가 없습니다. 확인된 월만 그래프에 표시했습니다."
    elif measured:
        label, summary = "플랫폼 반응 확인", "해당 플랫폼에서 측정한 반응 기록이 있습니다. 20대 남성 전체의 유행 여부와는 구분합니다."
    elif april is not None and april > 0 and all(row["shopping"] < april for row in followup):
        label, summary = "4월 이후 관심 약화", "5~10월 쇼핑 지수가 모두 4월보다 낮았습니다. 외부 자료로 확산 여부까지 확인하지는 못했습니다."
    elif april is not None and any(row["shopping"] > april for row in followup):
        label, summary = "후속 관심 상승", "4월보다 높은 관심 지수가 관측됐습니다. 외부 자료가 실제 유행을 확인하는지는 별도로 구분했습니다."
    else:
        label, summary = "확산 여부 미확인", "월별 관심 변화는 확인했지만 실제 유행을 확정할 외부 근거는 부족합니다."
    return series, {"label": label, "summary": summary, "peak_month": peak["month"] if peak else None,
                    "peak_value": peak["shopping"] if peak else None, "missing_months": missing,
                    "references": refs}


def compare(selection, review, outcome):
    result = review.get("result", {})
    ai = VERDICTS.get(result.get("verdict"), "AI 검토 미완료")
    baseline = VERDICTS[selection["status"]]
    contribution = "AI 검토가 완료되지 않았습니다."
    if review.get("status") == "complete":
        contribution = ("수치 기준과 관찰 판단이 같았습니다. 반대 이유가 이후 자료와 맞는지 확인합니다."
                        if result["verdict"] == selection["status"]
                        else "수치 기준과 다른 판단을 냈습니다. 차이를 설명한 근거와 이후 결과를 함께 확인합니다.")
    return {"baseline": baseline, "ai": ai, "observed": outcome["summary"],
            "contribution": contribution, "assessment": "설명의 도움 여부 검토 전", "checks": []}


class MonthlyService:
    def __init__(self, root, run_dir, manifest_path, provider="cloud", naver_client=None):
        self.root, self.run_dir = Path(root), Path(run_dir)
        self.manifest_path, self.provider = Path(manifest_path), provider
        self.naver = naver_client

    def load(self, name, default=None):
        return read_json(self.run_dir / name, default)

    def case_dir(self, i):
        return self.run_dir / "cases" / f"{i + 1:02}"

    def client(self):
        if self.naver is None:
            self.naver = NaverClient(self.root, provider=self.provider)
        return self.naver

    def prepare(self):
        manifest = validate_manifest(read_json(self.manifest_path))
        plan = {"schema_version": POLICY, "year": 2025, "provider": self.provider,
                "initial": {"start": "2025-03-01", "end": "2025-04-30"},
                "followup": {"start": "2025-03-01", "end": "2025-10-31"},
                "growth_threshold_pct": 20, "cases": [{"keyword": c["keyword"], "definition": c["definition"]} for c in manifest["cases"]],
                "selection_method": "외부 기록을 참고해 고른 과거 사례. 결과를 알고 구성한 설명용 사례이며 무작위 성능 평가가 아님."}
        existing = self.load("plan.json")
        if existing and existing != plan:
            raise ValueError("기존 사례·기간·정책을 바꾸지 않습니다. 새 실행 폴더를 사용하세요.")
        sources = self.load("sources.json")
        if sources and sources != manifest:
            raise ValueError("출처 선정 기록이 변경됐습니다. 새 실행 폴더를 사용하세요.")
        if not existing:
            save(self.run_dir / "plan.json", plan)
            save(self.run_dir / "sources.json", manifest)
        return plan

    def _records(self, name, end):
        records = self.load(name)
        if not isinstance(records, dict) or set(records) != {"shopping", "search"}:
            raise ValueError("검색·쇼핑 요청 기록이 필요합니다.")
        keywords = [c["keyword"] for c in self.load("plan.json")["cases"]]
        for ch, record in records.items():
            validate_record(record, ch, keywords, end)
        return records

    def collect(self):
        plan = self.prepare()
        if self.load("frozen.json"):
            self.verify_initial()
            return self.status()
        keywords = [c["keyword"] for c in plan["cases"]]
        records = {ch: self.client().fetch(ch, keywords, "2025-03-01", "2025-04-30", self.run_dir / "requests", time_unit="month")
                   for ch in ("shopping", "search")}
        for ch, record in records.items():
            validate_record(record, ch, keywords, "2025-04-30")
        save(self.run_dir / "initial-requests.json", records)
        bundles = [build_monthly_bundle(case, records) for case in plan["cases"]]
        for i, bundle in enumerate(bundles):
            save(self.case_dir(i) / "bundle.json", bundle)
        save(self.run_dir / "frozen.json", {"frozen_at": now(), "plan_sha256": digest(plan),
             "sources_sha256": digest(self.load("sources.json")), "requests_sha256": digest(records),
             "bundle_sha256": [digest(b) for b in bundles], "payload_sha256": [digest(build_payload(b)) for b in bundles]})
        save(self.run_dir / "claude-input-preview.json", [build_payload(b) for b in bundles])
        return self.status()

    def verify_initial(self):
        self.prepare()
        frozen = self.load("frozen.json")
        if not frozen:
            raise ValueError("3~4월 입력을 먼저 수집해야 합니다.")
        for name, key in (("plan.json", "plan_sha256"), ("sources.json", "sources_sha256"), ("initial-requests.json", "requests_sha256")):
            if digest(self.load(name)) != frozen[key]:
                raise ValueError("고정된 입력이 변경됐습니다: " + name)
        records = self._records("initial-requests.json", "2025-04-30")
        for i, case in enumerate(self.load("plan.json")["cases"]):
            bundle = read_json(self.case_dir(i) / "bundle.json")
            if (bundle != build_monthly_bundle(case, records) or digest(bundle) != frozen["bundle_sha256"][i]
                    or digest(build_payload(bundle)) != frozen["payload_sha256"][i]):
                raise ValueError("초기 근거·AI 입력이 고정 이후 달라졌습니다.")
        return frozen

    def review(self, client=None):
        self.verify_initial()
        if self.load("completion.json"):
            self.verify_complete()
        reviews = [run_review(self.root, self.case_dir(i), read_json(self.case_dir(i) / "bundle.json"), client)
                   for i in range(3)]
        return {"status": "complete" if all(r["status"] == "complete" for r in reviews) else "incomplete",
                "cases": [r["status"] for r in reviews]}

    def retry_review(self, index, client=None):
        """Explicit CLI action only: preserve a failed attempt, allow ONE new call."""
        self.verify_initial()
        if index not in (0, 1, 2) or self.load("completion.json"):
            raise ValueError("완료 전 실패한 사례 하나만 명시적으로 재실행할 수 있습니다.")
        case = self.case_dir(index)
        old = read_json(case / "review.json", {})
        if old.get("status") != "failed":
            raise ValueError("실패 상태가 아닙니다. 정상·진행 중 응답은 재호출하지 않습니다.")
        from uuid import uuid4
        archive = case / "attempts" / uuid4().hex
        archive.mkdir(parents=True, exist_ok=False)
        for name in ("claude-request.json", "review-partial.json", "review-partial.json.tmp"):
            content = read_json(case / name)
            if content is not None:
                save(archive / name, content)
        save(archive / "retry.json", {"at": now(), "reason": "명시적 retry-review 명령으로 실패한 호출 1회 추가 실행",
                                     "previous_input_sha256": old["input_sha256"]})
        source, target = (case / "review.json").resolve(), (archive / "review.json").resolve()
        root = self.run_dir.resolve()
        if not source.is_relative_to(root) or not target.is_relative_to(root):
            raise ValueError("실행 폴더 밖으로 기록을 이동할 수 없습니다.")
        source.rename(target)
        return run_review(self.root, case, read_json(case / "bundle.json"), client)

    def evaluate(self):
        frozen = self.verify_initial()
        reviews = [read_json(self.case_dir(i) / "review.json", {}) for i in range(3)]
        if any(r.get("status") != "complete" or r.get("input_sha256") != frozen["payload_sha256"][i] for i, r in enumerate(reviews)):
            raise ValueError("세 AI 판단이 정상 저장된 뒤 후속 자료를 조회합니다.")
        if date(2025, 10, 31) >= datetime.now(ZoneInfo("Asia/Seoul")).date():
            raise ValueError("관측 기간이 아직 끝나지 않았습니다.")
        completion = self.load("completion.json")
        if completion:
            self.verify_complete()
            return self.status()
        keywords = [c["keyword"] for c in self.load("plan.json")["cases"]]
        records = {ch: self.client().fetch(ch, keywords, "2025-03-01", "2025-10-31", self.run_dir / "requests", time_unit="month")
                   for ch in ("shopping", "search")}
        for ch, record in records.items():
            validate_record(record, ch, keywords, "2025-10-31")
        save(self.run_dir / "followup-requests.json", records)
        save(self.run_dir / "completion.json", {"completed_at": now(), "followup_sha256": digest(records),
                                                "review_sha256": [digest(r) for r in reviews]})
        return self.status()

    def verify_complete(self):
        self.verify_initial()
        completion = self.load("completion.json")
        if not completion:
            raise ValueError("후속 자료 수집이 완료되지 않았습니다.")
        self._records("followup-requests.json", "2025-10-31")
        if digest(self.load("followup-requests.json")) != completion["followup_sha256"]:
            raise ValueError("후속 원자료가 변경됐습니다.")
        for i in range(3):
            if digest(read_json(self.case_dir(i) / "review.json")) != completion["review_sha256"][i]:
                raise ValueError("저장된 초기 AI 응답이 변경됐습니다.")

    def export(self):
        from .monthly_report import write_monthly_exports
        self.verify_initial()
        plan, sources = self.load("plan.json"), self.load("sources.json")
        records = None
        if self.load("completion.json"):
            self.verify_complete()
            records = self.load("followup-requests.json")
        cases = []
        for i, definition in enumerate(sources["cases"]):
            bundle = read_json(self.case_dir(i) / "bundle.json")
            review = read_json(self.case_dir(i) / "review.json", {"status": "not_run"})
            selection = bundle["features"]["shopping"]
            if records:
                series, outcome = monthly_outcome(definition, records)
            else:
                series = [{"month": f"2025-{m:02}", "shopping": None, "search": None} for m in range(3, 11)]
                outcome = {"label": "후속 자료 미수집", "summary": "AI 판단 저장 후 월별 결과를 연결합니다.", "peak_month": None,
                           "peak_value": None, "missing_months": [], "references": definition.get("references", [])}
            comparison = compare(selection, review, outcome)
            annotation = read_json(self.case_dir(i) / "assessment.json")
            if annotation:
                if annotation.get("review_sha256") != digest(review) or annotation.get("followup_sha256") != digest(records):
                    raise ValueError("사후 검토가 현재 원자료·AI 응답과 연결되지 않습니다.")
                comparison.update({k: annotation[k] for k in ("contribution", "assessment", "checks")})
            presentation = read_json(self.case_dir(i) / "presentation.json")
            if presentation:
                if presentation.get("review_sha256") != digest(review):
                    raise ValueError("화면용 요약이 현재 AI 응답과 연결되지 않습니다.")
                review = deepcopy(review)
                review["result"]["display_summary"] = presentation["summary"]
                for kind in ("support", "against"):
                    if len(presentation[kind]) != len(review["result"][kind]):
                        raise ValueError("화면용 요약의 근거 개수가 원문과 다릅니다.")
                    for item, short in zip(review["result"][kind], presentation[kind]):
                        item["display_text"] = short
                review["display_note"] = "화면용 문장은 Codex가 줄여 정리함. 실제 API 응답 원문은 response.text에 보존."
            cases.append({"keyword": definition["keyword"], "definition": definition["definition"], "selection": selection,
                          "review": review, "series": series, "outcome": outcome, "comparison": comparison,
                          "provenance": {"policy": POLICY, "cutoff": "2025-05-01", "initial": self.load("initial-requests.json"),
                                         "followup": records, "frozen": self.load("frozen.json"), "bundle": bundle,
                                         "assessment": annotation, "presentation": presentation, "case_selection": plan["selection_method"]}})
        report = {"schema_version": POLICY, "year": 2025,
                  "generated_at": self.load("completion.json", self.load("frozen.json")).get("completed_at", self.load("frozen.json")["frozen_at"]),
                  "retrospective_note": NOTE, "cases": cases}
        return write_monthly_exports(self.run_dir, report)

    def status(self):
        return {"run_dir": str(self.run_dir.resolve()), "policy": POLICY, "initial_frozen": bool(self.load("frozen.json")),
                "followup_complete": bool(self.load("completion.json")),
                "cases": [{"keyword": c["keyword"], "review": read_json(self.case_dir(i) / "review.json", {}).get("status", "not_run")}
                          for i, c in enumerate(self.load("plan.json", {}).get("cases", []))]}
