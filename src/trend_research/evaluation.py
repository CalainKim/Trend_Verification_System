"""Validate final model answers and score a frozen, explicitly selected cohort.

Validation has no access to labels. Citation checks establish referential integrity,
not factual entailment. Numeric flags are review hints, never automatic truth labels.
Only ``evaluate`` receives truth, after the runner has frozen predictions.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import json
import math
import re
from statistics import median
from typing import Mapping


VERDICTS = {"WATCH", "NOT_SUPPORTED", "HOLD"}
PREDICTIONS = {"WATCH": "persist", "NOT_SUPPORTED": "fade"}
FAILURE_STATUSES = {"failed", "invalid", "budget_skipped", "interrupted"}
_FIELDS = {"verdict", "summary", "support", "against", "unknowns"}
_NUMBER = re.compile(r"(?<![0-9A-Za-z_.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?![0-9A-Za-z_.])")
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T[^\s\"']+)?\b")


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 20000


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError("nonfinite_json_number")


def _number_tokens(text):
    """Normalize numeric spellings without pretending to check units or meaning."""
    clean = _ISO_DATE.sub(" ", text)
    found = {}
    for match in _NUMBER.finditer(clean):
        token = match.group()
        percent = token.endswith("%")
        try:
            normalized = str(Decimal(token.rstrip("%").replace(",", "")).normalize())
        except InvalidOperation:
            continue
        found[(normalized, percent)] = token
    return found


def _evidence_map(prepared):
    evidence = prepared.get("evidence") if isinstance(prepared, dict) else None
    if not isinstance(evidence, list):
        raise ValueError("prepared_evidence_must_be_a_list")
    result = {}
    for item in evidence:
        if not isinstance(item, dict) or not _text(item.get("id")):
            raise ValueError("prepared_evidence_id_invalid")
        if item["id"] in result:
            raise ValueError("prepared_evidence_id_duplicate")
        observation = item.get("observation", item.get("text", ""))
        result[item["id"]] = (observation if isinstance(observation, str)
                              else json.dumps(observation, ensure_ascii=False, allow_nan=False))
    return result


def validate_result(text: str, prepared: dict, finish_reason: str) -> dict:
    """Return result/errors/status, accepting either provider's normal finish code.

    An invalid response remains invalid; it is never converted into ``HOLD``.
    A sole outer Markdown JSON fence is tolerated, but surrounding prose is not.
    """
    sources = _evidence_map(prepared)
    errors = []
    result = None
    if finish_reason not in {"stop", "end_turn"}:
        errors.append("response_not_complete")
    if not isinstance(text, str) or not text.strip() or len(text) > 131072:
        errors.append("final_text_missing_or_oversized")
    else:
        payload = text.strip()
        fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", payload, re.DOTALL | re.IGNORECASE)
        if fence:
            payload = fence.group(1).strip()
        try:
            result = json.loads(payload, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        except (ValueError, TypeError, RecursionError):
            errors.append("invalid_json")
        if not isinstance(result, dict):
            errors.append("result_must_be_object")
        else:
            if set(result) != _FIELDS:
                errors.append("result_fields_mismatch")
            if not isinstance(result.get("verdict"), str) or result["verdict"] not in VERDICTS:
                errors.append("invalid_verdict")
            if not _text(result.get("summary")):
                errors.append("invalid_summary")
            for side in ("support", "against"):
                claims = result.get(side)
                if not isinstance(claims, list) or len(claims) > 30:
                    errors.append(f"invalid_{side}")
                    continue
                for index, claim in enumerate(claims):
                    prefix = f"{side}[{index}]"
                    if not isinstance(claim, dict) or set(claim) != {"text", "evidence_ids"}:
                        errors.append(f"{prefix}:invalid_claim")
                        continue
                    if not _text(claim["text"]):
                        errors.append(f"{prefix}:invalid_text")
                    ids = claim["evidence_ids"]
                    if (not isinstance(ids, list) or not ids
                            or any(not _text(eid) for eid in ids)):
                        errors.append(f"{prefix}:invalid_evidence_ids")
                    elif len(set(ids)) != len(ids):
                        errors.append(f"{prefix}:duplicate_evidence_ids")
                    elif any(eid not in sources for eid in ids):
                        errors.append(f"{prefix}:unknown_evidence_id")
            unknowns = result.get("unknowns")
            if (not isinstance(unknowns, list) or len(unknowns) > 30
                    or any(not _text(item) for item in unknowns)):
                errors.append("invalid_unknowns")
    if errors:
        return {"status": "invalid", "result": None,
                "errors": list(dict.fromkeys(errors)), "warnings": [], "numeric_flags": []}

    flags = []
    # Scan claims against their cited evidence; a summary has no per-sentence IDs,
    # so its numeric text can only be checked against the complete evidence packet.
    checks = [("summary", result["summary"], list(sources))]
    for side in ("support", "against"):
        checks.extend((f"{side}[{i}]", claim["text"], claim["evidence_ids"])
                      for i, claim in enumerate(result[side]))
    for field, claim_text, ids in checks:
        observed_numbers = _number_tokens("\n".join(sources[eid] for eid in ids))
        for normalized, spelling in _number_tokens(claim_text).items():
            if normalized not in observed_numbers:
                flags.append({"field": field, "number": spelling,
                              "evidence_ids": ids, "kind": "number_not_literal_in_cited_evidence"})
    warnings = (["Numeric flags require manual review: arithmetic, units, and semantic support are not automatically verified."]
                if flags else [])
    return {"status": "complete", "result": result, "errors": [],
            "warnings": warnings, "numeric_flags": flags}


def _finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _wilson(k, n):
    if not n:
        return None
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, centre - half), min(1.0, centre + half)]


def evaluate(records: list, labels: Mapping[str, str], expected_case_ids: list[str]) -> dict:
    """Score one provider/view against a frozen cohort, retaining technical failure.

    ``records`` contains final case records, not an attempt/event log. Retry charges
    must already be aggregated by the runner. Extra labels are permitted for scoring
    a subset of a sealed benchmark; missing labels and duplicate records are errors.
    """
    if (not isinstance(expected_case_ids, list)
            or any(not _text(cid) for cid in expected_case_ids)
            or len(set(expected_case_ids)) != len(expected_case_ids)):
        raise ValueError("expected_case_ids_must_be_unique_strings")
    if not isinstance(labels, Mapping):
        raise ValueError("labels_must_be_mapping")
    expected = set(expected_case_ids)
    if expected - set(labels):
        raise ValueError("missing_truth_labels")
    if any(not isinstance(labels[cid], str) or labels[cid] not in {"persist", "fade"}
           for cid in expected):
        raise ValueError("unsupported_truth_label")
    if not isinstance(records, list):
        raise ValueError("records_must_be_list")
    indexed = {}
    for record in records:
        if not isinstance(record, dict) or not _text(record.get("case_id")):
            raise ValueError("record_case_id_invalid")
        cid = record["case_id"]
        if cid not in expected:
            raise ValueError("unexpected_record_case_id")
        if cid in indexed:
            raise ValueError("duplicate_record_case_id")
        if (not isinstance(record.get("status"), str)
                or record["status"] not in FAILURE_STATUSES | {"complete"}):
            raise ValueError("unsupported_record_status")
        indexed[cid] = record

    confusion = {truth: {pred: 0 for pred in ("WATCH", "NOT_SUPPORTED", "HOLD")}
                 for truth in ("persist", "fade")}
    failed_by_truth = {truth: 0 for truth in ("persist", "fade")}
    status_counts = Counter({key: 0 for key in ("complete", "failed", "invalid", "budget_skipped", "interrupted", "missing")})
    correct = wrong = held = 0
    times, actual_costs, accounted_costs = [], [], []
    reserved_cost_count = 0
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    usage_record_counts = {key: 0 for key in usage_totals}
    complete_usage_count = 0
    numeric_flag_count = 0
    invalid_evidence_id_count = 0
    for cid in expected_case_ids:
        truth = labels[cid]
        record = indexed.get(cid)
        if record is None:
            status_counts["missing"] += 1
            failed_by_truth[truth] += 1
            continue
        elapsed = record.get("elapsed_seconds")
        if _finite_nonnegative(elapsed):
            times.append(elapsed)
        actual_cost = record.get("cost_usd")
        accounted_cost = record.get("estimated_cost_usd")
        if _finite_nonnegative(actual_cost):
            actual_costs.append(actual_cost)
            accounted_costs.append(actual_cost)
        elif _finite_nonnegative(accounted_cost):
            accounted_costs.append(accounted_cost)
            reserved_cost_count += 1
        usage = record.get("usage", {})
        if isinstance(usage, dict):
            if record.get("usage_complete") is True:
                complete_usage_count += 1
            for key in usage_totals:
                value = usage.get(key)
                if type(value) is int and value >= 0:
                    usage_totals[key] += value
                    usage_record_counts[key] += 1
        flags = record.get("numeric_flags", [])
        if isinstance(flags, list):
            numeric_flag_count += len(flags)
        errors = record.get("validation_errors", record.get("errors", []))
        if isinstance(errors, list):
            invalid_evidence_id_count += sum(isinstance(e, str) and "unknown_evidence_id" in e for e in errors)
        status = record["status"]
        result = record.get("result")
        verdict = result.get("verdict") if isinstance(result, dict) else None
        # A supposedly complete record with no valid answer is still not a HOLD.
        if status == "complete" and (not isinstance(verdict, str) or verdict not in VERDICTS):
            status = "invalid"
        status_counts[status] += 1
        if status != "complete":
            failed_by_truth[truth] += 1
            continue
        confusion[truth][verdict] += 1
        if verdict == "HOLD":
            held += 1
        elif PREDICTIONS[verdict] == truth:
            correct += 1
        else:
            wrong += 1

    n = len(expected_case_ids)
    answered = correct + wrong
    failed = sum(failed_by_truth.values())
    actual_persist = sum(labels[cid] == "persist" for cid in expected_case_ids)
    actual_fade = n - actual_persist
    tp = confusion["persist"]["WATCH"]
    fp = confusion["fade"]["WATCH"]
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, actual_persist)
    return {
        "n_cases": n, "n_answered": answered, "n_complete": status_counts["complete"],
        "n_hold": held, "n_failed": failed, "n_missing": status_counts["missing"],
        "n_recorded_failures": failed - status_counts["missing"],
        "correct": correct, "wrong": wrong,
        "coverage": _ratio(answered, n), "completion_rate": _ratio(status_counts["complete"], n),
        "answered_accuracy": _ratio(correct, answered),
        "answered_accuracy_ci95": _wilson(correct, answered),
        "ci_interpretation": "Descriptive binomial interval only; same-date/product dependence is not accounted for, so this is not evidence of temporal generalization.",
        "correct_rate": _ratio(correct, n), "wrong_rate": _ratio(wrong, n),
        "hold_rate": _ratio(held, n), "failure_rate": _ratio(failed, n),
        "persist_precision": precision, "persist_recall": recall,
        "persist_f1": (2 * precision * recall / (precision + recall)
                       if precision is not None and recall is not None and precision + recall
                       else (0.0 if precision == 0.0 and recall == 0.0 else None)),
        "actual_persist": actual_persist, "actual_fade": actual_fade,
        "confusion": confusion, "failures_by_truth": failed_by_truth,
        "status_counts": dict(status_counts),
        "elapsed_seconds_total": sum(times) if times else None,
        "elapsed_seconds_mean": sum(times) / len(times) if times else None,
        "elapsed_seconds_median": median(times) if times else None,
        "elapsed_record_count": len(times),
        # Legacy cost fields are known actual-cost subtotals, never reservations.
        "cost_total_usd": sum(actual_costs) if actual_costs else None,
        "cost_mean_usd": sum(actual_costs) / len(actual_costs) if actual_costs else None,
        "cost_record_count": len(actual_costs),
        "actual_cost_total_usd": sum(actual_costs) if n and len(actual_costs) == n else None,
        "actual_cost_known_subtotal_usd": sum(actual_costs) if actual_costs else None,
        "actual_cost_record_count": len(actual_costs),
        "actual_cost_missing_count": n - len(actual_costs),
        "actual_cost_complete": bool(n and len(actual_costs) == n),
        "accounted_cost_total_usd": sum(accounted_costs) if n and len(accounted_costs) == n else None,
        "accounted_cost_known_subtotal_usd": sum(accounted_costs) if accounted_costs else None,
        "accounted_cost_record_count": len(accounted_costs),
        "accounted_cost_missing_count": n - len(accounted_costs),
        "accounted_cost_complete": bool(n and len(accounted_costs) == n),
        "reserved_cost_record_count": reserved_cost_count,
        "cost_interpretation": "Actual costs use reported billable usage. Accounted costs additionally include conservative reservations for unknown charges, not verified spend. Partial known subtotals are not cohort totals. GPU wall-clock/storage costs require the separate runtime record.",
        "usage": {key: usage_totals[key] if usage_record_counts[key] else None for key in usage_totals},
        "usage_record_counts": usage_record_counts,
        "usage_complete_record_count": complete_usage_count,
        "usage_complete": bool(n and complete_usage_count == n),
        "usage_interpretation": "Token sums contain known usage only. A failed attempt without usage keeps usage_complete false even if a later retry succeeds.",
        "numeric_review_flag_count": numeric_flag_count,
        "invalid_evidence_id_count": invalid_evidence_id_count,
        "evidence_check_interpretation": "Valid IDs and literal numeric matches do not establish factual support. Numeric flags require human inspection.",
    }
