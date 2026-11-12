"""Strict input contracts and a deterministic, cutoff-safe frozen search corpus."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

VERSION = "candidate-verification-v1"
CONDITIONS = ("with_interview", "without_interview")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def unique_json(text):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON field")
            out[key] = value
        return out
    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("Missing or unsupported fields")


def text(value, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("Expected nonempty bounded text")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise ValueError("Invalid identifier")
    return value


def stamp(value):
    if not isinstance(value, str):
        raise ValueError("Expected ISO timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return result


def scope(value):
    fields(value, ("market", "gender", "age_min", "age_max", "category"))
    for key in ("market", "gender", "category"):
        text(value[key], 80)
    lo, hi = value["age_min"], value["age_max"]
    if (lo is None) != (hi is None):
        raise ValueError("Both age bounds must be known or unknown")
    if lo is not None and (type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi <= 120):
        raise ValueError("Invalid age scope")


def scope_relation(actual, target):
    mismatch = any(actual[k] not in (target[k], "UNKNOWN") for k in ("market", "category"))
    mismatch |= actual["gender"] not in (target["gender"], "all", "UNKNOWN")
    if actual["age_min"] is not None and target["age_min"] is not None:
        mismatch |= actual["age_max"] < target["age_min"] or actual["age_min"] > target["age_max"]
    if mismatch:
        return "mismatch"
    return "direct" if actual == target else "context"


def validate_case(case):
    fields(case, ("case_id", "candidate", "definition", "claim", "cutoff", "scope",
                  "initial_evidence_ids", "synthetic"), ("aliases",))
    identifier(case["case_id"])
    for key in ("candidate", "definition", "claim"):
        text(case[key])
    stamp(case["cutoff"])
    scope(case["scope"])
    if type(case["synthetic"]) is not bool:
        raise ValueError("Synthetic origin must be explicit")
    ids = case["initial_evidence_ids"]
    if not isinstance(ids, list) or len(ids) > 12 or len(set(ids)) != len(ids):
        raise ValueError("Invalid initial evidence IDs")
    for value in ids:
        identifier(value)
    aliases = case.get("aliases", [])
    if not isinstance(aliases, list) or len(aliases) > 10:
        raise ValueError("Invalid aliases")
    for value in aliases:
        text(value, 200)


def validate_criteria(criteria):
    if not isinstance(criteria, list) or len(criteria) > 12:
        raise ValueError("Invalid criteria")
    seen = set()
    for item in criteria:
        fields(item, ("id", "hypothesis", "question", "expected_evidence", "source_ref", "reviewed"),
               ("applicability", "counterexamples"))
        identifier(item["id"])
        if item["id"] in seen:
            raise ValueError("Duplicate criterion")
        seen.add(item["id"])
        for key in ("hypothesis", "question", "expected_evidence"):
            text(item[key])
        if type(item["reviewed"]) is not bool:
            raise ValueError("Criterion reviewed flag must be explicit")
        if item["source_ref"] is not None:
            text(item["source_ref"], 1000)
        if item["reviewed"] and not item["source_ref"]:
            raise ValueError("Reviewed criterion requires its source reference")
        if "applicability" in item:
            text(item["applicability"], 1500)
        if "counterexamples" in item:
            if not isinstance(item["counterexamples"], list) or len(item["counterexamples"]) > 6:
                raise ValueError("Invalid criterion counterexamples")
            for example in item["counterexamples"]:
                text(example, 1200)


def prepare_corpus(case, corpus):
    if not isinstance(corpus, list) or len(corpus) > 2000:
        raise ValueError("Invalid frozen corpus")
    docs = {}
    required = ("id", "kind", "title", "text", "source_url", "source_family_id", "repost_of",
                "observed_at", "published_at", "collected_at", "available_at", "scope", "synthetic")
    for doc in corpus:
        fields(doc, required, ("observations",))
        identifier(doc["id"])
        if doc["id"] in docs:
            raise ValueError("Duplicate evidence ID")
        if doc["kind"] not in ("observation", "interview_criterion", "label", "model_output"):
            raise ValueError("Unsupported corpus document kind")
        text(doc["title"], 300)
        text(doc["text"], 12000)
        url = urlsplit(doc["source_url"])
        if url.scheme not in ("http", "https") or not url.netloc or url.username or url.password:
            raise ValueError("Evidence requires a source URL without credentials")
        if doc["source_family_id"] is not None:
            identifier(doc["source_family_id"])
        if doc["repost_of"] is not None:
            identifier(doc["repost_of"])
        for key in ("observed_at", "published_at", "collected_at", "available_at"):
            if doc[key] is not None:
                stamp(doc[key])
        if doc["observed_at"] is None or doc["published_at"] is None or doc["collected_at"] is None:
            raise ValueError("Observation, publication, and collection timestamps are required")
        scope(doc["scope"])
        if type(doc["synthetic"]) is not bool or doc["synthetic"] != case["synthetic"]:
            raise ValueError("Do not mix synthetic and study evidence")
        observations = doc.get("observations", [])
        if not isinstance(observations, list) or len(observations) > 100:
            raise ValueError("Invalid observations")
        for observation in observations:
            fields(observation, ("at", "metric", "value", "unit"))
            stamp(observation["at"])
            text(observation["metric"], 100)
            text(observation["unit"], 100)
            if type(observation["value"]) not in (int, float) or not math.isfinite(observation["value"]):
                raise ValueError("Invalid measurement")
        docs[doc["id"]] = doc

    roots = {}
    for doc in corpus:
        seen, current = set(), doc
        while current["repost_of"]:
            if current["id"] in seen or current["repost_of"] not in docs:
                raise ValueError("Broken or cyclic repost chain")
            seen.add(current["id"])
            parent = docs[current["repost_of"]]
            if current["source_family_id"] != parent["source_family_id"]:
                raise ValueError("Reposts cannot claim a different source family")
            current = parent
        roots[doc["id"]] = current

    cutoff, eligible, excluded = stamp(case["cutoff"]), [], []
    for doc in corpus:
        relation = scope_relation(doc["scope"], case["scope"])
        reason = None
        if doc["kind"] != "observation" or roots[doc["id"]]["kind"] != "observation":
            reason = "non_observation"  # No interview, labels, or earlier answers in either arm.
        elif doc["available_at"] is None:
            reason = "availability_unverified"
        elif any(stamp(doc[k]) > cutoff for k in ("observed_at", "published_at", "collected_at", "available_at")):
            reason = "after_cutoff"
        elif any(stamp(x["at"]) > cutoff for x in doc.get("observations", [])):
            reason = "future_observation"
        elif relation == "mismatch":
            reason = "scope_mismatch"
        elif doc["repost_of"]:
            reason = "repost"
        if reason:
            excluded.append({"id": doc["id"], "reason": reason})
        else:
            eligible.append({**doc, "scope_relation": relation,
                             "independence": "unverified" if doc["source_family_id"] is None else "source_family_recorded"})
    allowed = {d["id"]: d for d in eligible}
    if any(i not in allowed for i in case["initial_evidence_ids"]):
        raise ValueError("Initial evidence is absent or excluded by corpus validation")
    return eligible, excluded


def tokens(value):
    return set(re.findall(r"[a-z0-9]+|[가-힣]+", value.lower()))


def search(corpus, query):
    """Stable lexical search, at most three unique non-repost documents."""
    text(query, 300)
    terms = tokens(query)
    scored = []
    for doc in corpus:
        score = len(terms & tokens(doc["title"] + " " + doc["text"]))
        if score:
            scored.append((score, doc["id"], doc))
    return [doc for _, _, doc in sorted(scored, key=lambda row: (-row[0], row[1]))[:3]]


def select_candidates(registrations, excluded_ids, excluded_family_ids, limit=6):
    """Prepare a deterministic study manifest from an explicitly reviewed family map.

    Family identities and exclusions are supplied, never guessed from names.
    This function does not collect cases, fabricate missing ones, or authorize
    model calls. ``development_family`` must be reviewed before registration.
    """
    if type(limit) is not int or not 1 <= limit <= 6:
        raise ValueError("Candidate selection limit must be between one and six")
    excluded_ids, excluded_family_ids = set(excluded_ids), set(excluded_family_ids)
    seen, eligible, excluded = set(), [], []
    for row in registrations:
        fields(row, ("case_id", "candidate_family_id", "trigger_at", "eligible",
                     "development_family", "synthetic", "source_sha256"))
        identifier(row["case_id"])
        identifier(row["candidate_family_id"])
        stamp(row["trigger_at"])
        if row["case_id"] in seen:
            raise ValueError("Duplicate candidate registration")
        seen.add(row["case_id"])
        for key in ("eligible", "development_family", "synthetic"):
            if type(row[key]) is not bool:
                raise ValueError("Candidate eligibility and origin must be explicit")
        if not isinstance(row["source_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["source_sha256"]):
            raise ValueError("Candidate requires a frozen source hash")
        reason = ("synthetic" if row["synthetic"] else "ineligible_trigger" if not row["eligible"]
                  else "development_family" if row["development_family"]
                  or row["candidate_family_id"] in excluded_family_ids
                  else "excluded_case" if row["case_id"] in excluded_ids else None)
        if reason:
            excluded.append({"case_id": row["case_id"], "reason": reason})
        else:
            eligible.append(row)
    ordered = sorted(eligible, key=lambda row: (stamp(row["trigger_at"]), row["case_id"]))
    selected, families = [], set()
    for row in ordered:
        if row["candidate_family_id"] in families:
            excluded.append({"case_id": row["case_id"], "reason": "same_candidate_family"})
        elif len(selected) < limit:
            selected.append(row)
            families.add(row["candidate_family_id"])
    manifest = {"schema_version": VERSION, "selection_rule": "earliest_eligible_trigger_then_case_id",
                "registrations_sha256": digest(sorted(registrations, key=lambda row: row["case_id"])),
                "excluded_ids": sorted(excluded_ids), "excluded_family_ids": sorted(excluded_family_ids),
                "required_count": limit, "selected": selected, "excluded": sorted(excluded, key=lambda row: row["case_id"]),
                "status": "ready_to_review" if len(selected) == limit else "insufficient_real_candidates"}
    manifest["manifest_sha256"] = digest(manifest)
    return manifest
