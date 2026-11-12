"""Scripted synthetic example, never a proxy for Claude/Qwen performance."""
from __future__ import annotations

import json


class ScriptedDemoClient:
    offline = True

    def generate(self, system, prompt):
        request = json.loads(prompt)
        stage = request["stage"]
        evidence = request["evidence"]
        initial = next((d for d in evidence if any(o["metric"] == "rank" for o in d.get("observations", []))), None)
        correction = next((d for d in evidence if any(o["metric"] == "distinct_original_sources"
                          and o["value"] == 1 for o in d.get("observations", []))), None)
        candidate = request["candidate"]["candidate"]
        if stage.startswith("search_plan"):
            second = stage.endswith("2")
            result = {"query": f"{candidate} 캠페인 정정" if second else f"{candidate} 순위 상승",
                      "purpose": "counterevidence" if second else "support",
                      "reason": "독립 확산의 다른 설명을 찾는다" if second else "초기 상승 자료의 맥락을 확인한다",
                      "request_another_search": not second}
        elif stage == "critic":
            result = {"assessment": "challenged" if correction else "supported",
                      "summary": "서로 다른 원출처 3개로 집계한 보고가 모두 같은 원본의 재게시라는 대조 결과가 초기 주장을 뒤집는다" if correction else "검색된 범위에서 초기 주장을 뒤집는 관측은 확인되지 않았다",
                      "counterarguments": [{"text": "정정 자료는 초기의 세 원출처가 실제로는 하나의 원본임을 확인한다. 이 근거 묶음에서 독립 관측 3개라는 주장은 성립하지 않는다",
                                            "evidence_ids": [correction["id"]]}] if correction else [],
                      "missed_evidence_ids": [correction["id"]] if correction else [],
                      "unsupported_claims": ["초기 관측만으로 노출의 독립성을 확정한 해석"] if correction else [],
                      "recommended_verdict": "REJECT" if correction else "CONFIRM"}
        else:
            rejected = stage == "final" and correction is not None
            result = {"verdict": "REJECT" if rejected else "CONFIRM" if initial else "HOLD",
                      "summary": "초기에 독립 원출처 3개로 기록된 관측은 모두 같은 원본의 재게시로 정정됐다. 제공된 묶음의 독립 관측 주장을 기각하며 미래 유행 여부를 기각하는 것은 아니다" if rejected else "초기 자료에는 대상 패널 순위 상승과 원출처 3개라는 집계가 있다. 이 집계에 근거해 현재 후보 주장을 잠정 지지한다" if initial else "대상에 맞는 과거 관측이 부족하다",
                      "support": [{"text": "초기 대상 관측에는 순위 상승과 서로 다른 원출처 3개라는 집계가 기록돼 있다",
                                   "evidence_ids": [initial["id"]]}] if initial else [],
                      "counter": [{"text": "원본 대조 결과 초기 세 원출처는 모두 한 원본의 재게시였으며, 서로 다른 원출처 수는 1개였다",
                                   "evidence_ids": [correction["id"]]}] if rejected else [],
                      "unknowns": [] if initial else [{"code": "missing_past_evidence", "detail": "대상 관측 자료가 필요하다"}],
                      "change_conditions": ["다른 원생산자의 대상 관측에서도 반응이 확인되면 다시 검토한다"]}
            if "criteria" in request:
                result["criterion_reviews"] = [{"criterion_id": c["id"],
                    "application_status": "applied" if c["reviewed"] else "applied_as_hypothesis",
                    "application_reason": "합성 데모에서 제공된 검토 전 가설을 자료에 대조했다. 실제 인터뷰 확정이 아니다.",
                    "supporting_evidence_ids": [initial["id"]] if initial else [],
                    "conflicting_evidence_ids": [correction["id"]] if rejected else []} for c in request["criteria"]]
            if stage == "final":
                result["reason_for_revision"] = ("CONFIRM에서 REJECT로 변경했다. 원본 대조에서 초기 세 관측이 모두 하나의 원출처로 확인돼, 제공된 묶음의 독립 관측 3개라는 주장이 반박됐다. 광고의 존재나 미래 반응의 부재 때문에 바꾼 것이 아니다."
                    if rejected else "초기 판정을 유지했다. 제한된 반대 근거 검색과 별도 반증에서 이를 뒤집는 관측을 찾지 못했으며, 이것이 반대 근거의 부재를 보장하지는 않는다.")
        return {"text": json.dumps(result, ensure_ascii=False), "actual_model": "scripted-synthetic-v1",
                "finish_reason": "stop", "usage": {"input_tokens": 0, "output_tokens": 0}, "usage_complete": True}


def load_example(root):
    from pathlib import Path
    folder = Path(root) / "data/examples/candidate-verification"
    return tuple(json.loads((folder / name).read_text(encoding="utf-8-sig"))
                 for name in ("case.json", "corpus.json", "criteria.json"))
