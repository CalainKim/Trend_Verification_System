"""Authorized live adapter with cumulative, append-only reservations.

Historical ledgers are never rewritten. Unknown API usage keeps its reservation.
GPU rental includes startup/idle time and is settled only by stopped verification;
this module does not start or stop a GPU.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
import uuid

from trend_research.providers import ModelConfig, create_client
from trend_research.runner import reservation, usage_cost, store_lock
from .engine import BudgetLimitReached, LiveExecutionDisabled, run_case, verify_run, write_once
from .inputs import CONDITIONS, digest, fields, identifier, stamp, unique_json

AUTH_VERSION = "candidate-verification-live-authorization-v1"
SOURCES = ("private/research-pilot/live/state.json",
           "private/research-pilot/forecast-v2/state.json",
           "docs/research/pilot-costs.json", "docs/research/forecast-v2-costs.json")
LEDGER = "private/candidate-live/budget"
CAPS = {"claude_usd": 2.0, "total_usd": 5.0, "a40_seconds": 7200.0}
CONSOLE_HEARTBEAT_MAX_SECONDS = 300


def read(path):
    return unique_json(Path(path).read_text(encoding="utf-8-sig"))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, *, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError("Invalid finite nonnegative budget value")
    return value


def audit_prior(root, expected_hashes=None):
    """Audit the two prior experiments; no calls or mutations are performed."""
    root = Path(root)
    hashes = {name: file_hash(root / name) for name in SOURCES}
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError("Historical budget sources changed or are incomplete")
    first, second, first_cost, second_cost = [read(root / name) for name in SOURCES]
    claude, unknown = 0.0, 0
    for state in (first, second):
        if state.get("demo") is not False:
            raise ValueError("Historical ledger must identify actual execution")
        for attempt in state["attempts"]:
            if attempt.get("provider") != "claude":
                continue
            actual = attempt.get("actual_claude_usd")
            if actual is None:
                unknown += 1
                claude += max(number(attempt.get("accounted_claude_usd", 0)),
                              number(attempt.get("reserved_claude_usd", 0)))
            else:
                claude += max(number(actual), number(attempt.get("accounted_claude_usd", actual)))
    claude = max(claude, number(first_cost.get("claude_usage_cost_usd", 0)))
    gpu_seconds, gpu_usd = 0.0, 0.0
    for state, cost in ((first, first_cost), (second, second_cost)):
        if cost.get("gpu_stopped") is not True:
            raise ValueError("Historical GPU session lacks stopped verification")
        start = stamp(cost["session_started_at_conservative"])
        stop = stamp(cost["stopped_verified_at"])
        if abs((stamp(state["a40_started_at"]) - start).total_seconds()) > 1:
            raise ValueError("GPU cost record does not match its historical session")
        elapsed = max(number(cost["elapsed_seconds_upper_estimate"]), (stop - start).total_seconds())
        if elapsed < 0:
            raise ValueError("Invalid historical GPU interval")
        gpu_seconds += elapsed
        gpu_usd += number(cost["rental_cost_estimate_usd"])
    storage = max(0.5, number(first.get("storage_reserved_usd", 0)),
                  number(second.get("storage_reserved_usd", 0)))
    return {"source_hashes": hashes, "claude_accounted_usd": claude,
            "gpu_seconds": gpu_seconds, "gpu_estimate_usd": gpu_usd,
            "storage_reserve_usd": storage, "unknown_claude_attempts": unknown,
            "remaining_claude_usd": CAPS["claude_usd"] - claude,
            "remaining_total_usd_including_storage_reserve": CAPS["total_usd"] - claude - gpu_usd - storage,
            "remaining_gpu_seconds": CAPS["a40_seconds"] - gpu_seconds,
            "cost_basis": "Recorded API usage and conservative stopped GPU estimates; not an invoice"}


def validate_config(config):
    if config.get("live_execution_enabled") is not True:
        raise LiveExecutionDisabled("Live configuration must be explicit, with separate authorization")
    fields(config["models"], ("claude", "qwen"))
    models = {name: ModelConfig(**value) for name, value in config["models"].items()}
    c, q = models["claude"], models["qwen"]
    if (c.provider != "anthropic" or c.model != "claude-sonnet-5-5" or c.effort != "low"
            or c.input_price_per_million != 2 or c.output_price_per_million != 10):
        raise ValueError("Claude settings must preserve the authorized pilot model and pricing")
    if (q.provider != "openai_compatible" or q.model != "Qwen/Qwen3-8B"
            or q.enable_thinking is not True or q.temperature != 0.6):
        raise ValueError("Qwen settings must preserve the authorized pilot model and sampling")
    if any(m.max_tokens > 8192 or m.timeout_seconds > 300 for m in models.values()):
        raise ValueError("Output and timeout caps cannot exceed the existing pilot")
    return models


class LiveLedger:
    def __init__(self, root, authorization, config, *, clock=None):
        self.root = Path(root)
        self.authorization, self.config = authorization, config
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        fields(authorization, ("schema_version", "authorization_id", "authorized_at", "max_stage_calls",
                               "max_recovery_calls", "source_hashes", "input_hashes", "config_hash",
                               "storage_reserve_usd", "rental_path"))
        if authorization["schema_version"] != AUTH_VERSION:
            raise ValueError("Unsupported live authorization")
        identifier(authorization["authorization_id"])
        stamp(authorization["authorized_at"])
        if (type(authorization["max_stage_calls"]) is not int
                or not 1 <= authorization["max_stage_calls"] <= 20
                or authorization["max_recovery_calls"] != 0):
            raise ValueError("This authorization permits at most 20 stage calls and no retries")
        fields(authorization["input_hashes"], ("case", "corpus", "criteria"))
        if authorization["config_hash"] != digest(config):
            raise ValueError("Model settings changed after authorization")
        self.models = validate_config(config)
        self.baseline = audit_prior(self.root, authorization["source_hashes"])
        self.storage = number(authorization["storage_reserve_usd"])
        if self.storage < self.baseline["storage_reserve_usd"]:
            raise ValueError("Existing storage reserve cannot be reduced")
        rental_path = Path(authorization["rental_path"])
        if rental_path.is_absolute() or ".." in rental_path.parts:
            raise ValueError("Rental record must be inside this worktree")
        self.rental_path = self.root / rental_path
        self.folder = self.root / LEDGER
        with store_lock(self.folder):
            auth_path = self.folder / "authorization.json"
            if auth_path.exists():
                if read(auth_path) != authorization:
                    raise ValueError("Do not reset or replace the live task authorization/ledger")
            else:
                if list(self.folder.glob("event-*.json")):
                    raise ValueError("Ledger events exist without their immutable authorization")
                write_once(auth_path, authorization)
                write_once(self.folder / "prior-budget-audit.json", self.baseline)

    def _events(self):
        if read(self.folder / "authorization.json") != self.authorization:
            raise ValueError("Live authorization was modified after initialization")
        events, previous = [], None
        for index, path in enumerate(sorted(self.folder.glob("event-*.json")), 1):
            event = read(path)
            checksum = event.pop("event_sha256", None)
            if (path.name != f"event-{index:05d}.json" or event["sequence"] != index
                    or event["previous_sha256"] != previous or digest(event) != checksum):
                raise ValueError("Live ledger integrity check failed")
            event["event_sha256"] = checksum
            events.append(event)
            previous = checksum
        return events

    def _append(self, events, kind, **payload):
        event = {"sequence": len(events) + 1, "at": self.clock().isoformat(), "kind": kind,
                 "previous_sha256": events[-1]["event_sha256"] if events else None, **payload}
        event["event_sha256"] = digest(event)
        write_once(self.folder / f"event-{event['sequence']:05d}.json", event)
        events.append(event)
        return event

    def _totals(self, events):
        attempts, rentals = {}, {}
        for e in events:
            if e["kind"] == "call_reserved":
                attempts[e["attempt_id"]] = e["reserved_claude_usd"]
            elif e["kind"] == "call_settled" and e["actual_claude_usd"] is not None:
                attempts[e["attempt_id"]] = e["actual_claude_usd"]
            elif e["kind"] == "gpu_reserved":
                rentals[e["session_id"]] = (e["reserved_seconds"], e["reserved_usd"])
            elif e["kind"] == "gpu_settled":
                rentals[e["session_id"]] = (e["elapsed_seconds"], e["cost_estimate_usd"])
        claude = self.baseline["claude_accounted_usd"] + sum(attempts.values())
        gpu_seconds = self.baseline["gpu_seconds"] + sum(v[0] for v in rentals.values())
        gpu_usd = self.baseline["gpu_estimate_usd"] + sum(v[1] for v in rentals.values())
        return {"stage_calls": len(attempts), "claude_accounted_usd": claude,
                "gpu_seconds": gpu_seconds, "gpu_estimate_usd": gpu_usd,
                "storage_reserve_usd": self.storage, "total_accounted_usd": claude + gpu_usd + self.storage}

    def _check(self, totals, *, reserve=0):
        if (totals["claude_accounted_usd"] + reserve > CAPS["claude_usd"] + 1e-12
                or totals["total_accounted_usd"] + reserve > CAPS["total_usd"] + 1e-12
                or totals["gpu_seconds"] > CAPS["a40_seconds"]):
            raise BudgetLimitReached("Cumulative financial or rental cap reached")

    def _rental(self, events, *, required=False, timeout=0):
        if not self.rental_path.exists():
            if required:
                raise BudgetLimitReached("Qwen requires an active recorded GPU rental")
            return
        rental = read(self.rental_path)
        fields(rental, ("session_id", "started_at", "deadline", "session_cap_seconds", "hourly_usd",
                        "status", "stopped_verified_at", "independent_stop_armed"), ("console_stop_supervision",))
        identifier(rental["session_id"])
        started, deadline = stamp(rental["started_at"]), stamp(rental["deadline"])
        seconds, rate = number(rental["session_cap_seconds"], minimum=1), number(rental["hourly_usd"], minimum=0.01)
        if (seconds > 1800 or rate > 1 or (deadline - started).total_seconds() > seconds
                or deadline <= started or started > self.clock() or type(rental["independent_stop_armed"]) is not bool
                or rental["status"] not in ("running", "stopped")):
            raise ValueError("Invalid GPU cap, deadline, or stop record")
        stop_control = {"mode": "independent_stop", "deadline": rental["deadline"]}
        if not rental["independent_stop_armed"]:
            supervision = rental.get("console_stop_supervision")
            fields(supervision, ("mode", "pod_id", "deadline", "confirmed_at"))
            identifier(supervision["pod_id"])
            confirmed = stamp(supervision["confirmed_at"])
            if (supervision["mode"] != "active_agent_console" or supervision["deadline"] != rental["deadline"]
                    or confirmed < started or confirmed > self.clock()):
                raise ValueError("Invalid explicit console stop supervision")
            if (rental["status"] == "running"
                    and (self.clock() - confirmed).total_seconds() > CONSOLE_HEARTBEAT_MAX_SECONDS):
                raise BudgetLimitReached("Console stop supervision heartbeat is stale; no further model call")
            stop_control = {**supervision, "heartbeat_max_seconds": CONSOLE_HEARTBEAT_MAX_SECONDS,
                            "automatic_stop_verified": False}
        session = rental["session_id"]
        reserved = next((e for e in events if e["kind"] == "gpu_reserved" and e["session_id"] == session), None)
        identity = {k: rental[k] for k in ("session_id", "started_at", "deadline", "session_cap_seconds", "hourly_usd")}
        if reserved and reserved["rental_identity"] != identity:
            raise ValueError("Do not reset an existing GPU rental clock")
        if not reserved:
            if any(e["kind"] == "gpu_reserved" and not any(
                    s["kind"] == "gpu_settled" and s["session_id"] == e["session_id"] for s in events) for e in events):
                raise BudgetLimitReached("A previous new GPU rental remains unclosed")
            prospective = self._totals(events)
            prospective["gpu_seconds"] += seconds
            prospective["total_accounted_usd"] += seconds / 3600 * rate
            self._check(prospective)
            self._append(events, "gpu_reserved", session_id=session, rental_identity=identity,
                         reserved_seconds=seconds, reserved_usd=seconds / 3600 * rate,
                         stop_control=stop_control)
        settled = next((e for e in events if e["kind"] == "gpu_settled" and e["session_id"] == session), None)
        if rental["status"] == "stopped":
            stop = stamp(rental["stopped_verified_at"])
            elapsed = (stop - started).total_seconds()
            if elapsed < 0 or stop > self.clock():
                raise ValueError("Invalid GPU stopped verification time")
            if settled and settled["stopped_verified_at"] != rental["stopped_verified_at"]:
                raise ValueError("GPU stopped verification cannot be rewritten")
            if not settled:
                self._append(events, "gpu_settled", session_id=session,
                             stopped_verified_at=rental["stopped_verified_at"], elapsed_seconds=elapsed,
                             cost_estimate_usd=elapsed / 3600 * rate)
        elif settled:
            raise ValueError("A stopped rental cannot be restarted under the same session ID")
        if rental["status"] == "running" and (rental["stopped_verified_at"] is not None or self.clock() >= deadline):
            raise BudgetLimitReached("GPU stop deadline reached; record verified shutdown before further calls")
        if required and (rental["status"] != "running" or self.clock() < started
                         or self.clock().timestamp() + timeout + min(15, timeout) + 10 >= deadline.timestamp()):
            raise BudgetLimitReached("GPU deadline cannot accommodate the full request and shutdown margin")
        return stop_control

    def status(self):
        with store_lock(self.folder):
            audit_prior(self.root, self.authorization["source_hashes"])
            events = self._events()
            self._rental(events)
            return {**self._totals(events), "caps": CAPS, "max_stage_calls": self.authorization["max_stage_calls"],
                    "ledger_events": len(events), "authorization_id": self.authorization["authorization_id"]}

    def begin_arm(self, case, corpus, criteria, condition, model_name, config, diagnostic_from=None):
        if condition not in CONDITIONS or model_name not in self.models:
            raise ValueError("Unapproved comparison arm")
        if ({"case": digest(case), "corpus": digest(corpus), "criteria": digest(criteria)}
                != self.authorization["input_hashes"] or config != self.models[model_name]):
            raise ValueError("Inputs or settings changed after authorization")
        key = model_name + "|" + condition
        parent = None
        if diagnostic_from is not None:
            from .engine import LIVE_PROMPT_VERSION
            parent = verify_run(diagnostic_from)
            expected_hashes = self.authorization["input_hashes"]
            if (model_name != "qwen" or condition != "with_interview"
                    or parent.get("status") != "schema_error"
                    or parent.get("demo") is not False
                    or parent.get("condition") != condition
                    or parent.get("model", {}).get("comparison_slot") != model_name
                    or parent["model"].get("execution_kind") != "live_provider"
                    or parent["model"].get("settings") != config.public_dict()
                    or any(parent.get("hashes", {}).get(k) != v for k, v in expected_hashes.items())
                    or parent.get("budget_authorization", {}).get("authorization_hash") != digest(self.authorization)
                    or parent.get("prompt_version") == LIVE_PROMPT_VERSION):
                raise ValueError("Manual diagnostic requires the matching failed Qwen interview arm and a new prompt version")
            key += "|diagnostic1"
        with store_lock(self.folder):
            audit_prior(self.root, self.authorization["source_hashes"])
            events = self._events()
            if parent is not None:
                if any(e["kind"] == "diagnostic_authorized" for e in events):
                    raise BudgetLimitReached("One manual diagnostic is already recorded for this authorization")
                if self.authorization["max_stage_calls"] - self._totals(events)["stage_calls"] < 5:
                    raise BudgetLimitReached("Manual diagnostic requires five remaining original stage calls")
                parent_attempts = {r["attempt_id"] for r in parent.get("budget_receipts", [])
                                   if r.get("kind") == "call_reserved"}
                ledger_attempts = {e["attempt_id"] for e in events if e["kind"] == "call_reserved"
                                   and e["arm"] == "qwen|with_interview"}
                if not parent_attempts or not parent_attempts <= ledger_attempts:
                    raise ValueError("Failed parent is not from this original task ledger")
            if any(e["kind"] == "arm_started" and e["arm"] == key for e in events):
                raise BudgetLimitReached("This arm was already attempted; retries are not authorized")
            self._rental(events, required=model_name == "qwen", timeout=config.timeout_seconds)
            self._check(self._totals(events))
            if parent is not None:
                self._append(events, "diagnostic_authorized", arm=key,
                             parent_run_id=parent["run_id"], parent_record_sha256=parent["record_sha256"],
                             parent_prompt_version=parent["prompt_version"], prompt_version=LIVE_PROMPT_VERSION,
                             reason="Explicitly authorized one manual contract-clarification diagnostic; not an automatic retry",
                             original_max_stage_calls=self.authorization["max_stage_calls"], automatic_retries=0)
            self._append(events, "arm_started", arm=key, input_hashes=self.authorization["input_hashes"])
        return key

    def reserve(self, arm, config, system, prompt):
        with store_lock(self.folder):
            audit_prior(self.root, self.authorization["source_hashes"])
            events = self._events()
            stop_control = self._rental(events, required=config.provider == "openai_compatible", timeout=config.timeout_seconds)
            totals = self._totals(events)
            if totals["stage_calls"] >= self.authorization["max_stage_calls"]:
                raise BudgetLimitReached("Authorized stage-call limit reached")
            reserve = reservation(config, system, prompt)
            self._check(totals, reserve=reserve)
            return self._append(events, "call_reserved", arm=arm, attempt_id=uuid.uuid4().hex,
                                prompt_hash=digest({"system": system, "prompt": prompt}),
                                reserved_claude_usd=reserve, model=config.model,
                                provider=config.provider, gpu_stop_control=stop_control)

    def settle(self, receipt, config, response):
        actual = usage_cost(config, response) if isinstance(response, dict) else None
        with store_lock(self.folder):
            events = self._events()
            if any(e["kind"] == "call_settled" and e["attempt_id"] == receipt["attempt_id"] for e in events):
                raise ValueError("Attempt already settled")
            return self._append(events, "call_settled", attempt_id=receipt["attempt_id"],
                                actual_claude_usd=actual,
                                usage_complete=isinstance(response, dict) and response.get("usage_complete") is True,
                                accounted_claude_usd=actual if actual is not None else receipt["reserved_claude_usd"])


class BudgetedClient:
    """Transport adapter: reserve durably before constructing/calling a provider."""
    def __init__(self, ledger, config, credentials_root, *, client_factory=create_client, diagnostic_from=None):
        self.ledger, self.config = ledger, config
        self.credentials_root, self.client_factory = credentials_root, client_factory
        self.client, self.arm, self.receipts = None, None, []
        self.diagnostic_from = diagnostic_from

    def bind(self, case, corpus, criteria, condition, model_name, config):
        if self.arm is not None or config != self.config:
            raise ValueError("Live adapter cannot be reused across arms")
        self.arm = self.ledger.begin_arm(case, corpus, criteria, condition, model_name, config, self.diagnostic_from)

    def public_authorization(self):
        return {"authorization_id": self.ledger.authorization["authorization_id"],
                "authorization_hash": digest(self.ledger.authorization), "ledger": LEDGER,
                "caps": CAPS, "max_stage_calls": self.ledger.authorization["max_stage_calls"]}

    def generate(self, system, prompt):
        if self.arm is None:
            raise LiveExecutionDisabled("Live adapter is not bound to an authorized input arm")
        receipt = self.ledger.reserve(self.arm, self.config, system, prompt)
        self.receipts.append(receipt)
        response = None
        try:
            if self.client is None:
                self.client = self.client_factory(self.config, self.credentials_root)
            response = self.client.generate(system, prompt)
            return response
        finally:
            self.receipts.append(self.ledger.settle(receipt, self.config, response))

    def close(self):
        if self.client is not None:
            self.client.close()


def run_live(case, corpus, criteria, *, root, authorization, config, model_name, condition,
             output_dir, credentials_root=None, client_factory=create_client, diagnostic_from=None):
    ledger = LiveLedger(root, authorization, config)
    model = ledger.models[model_name]
    client = BudgetedClient(ledger, model, credentials_root or root, client_factory=client_factory,
                            diagnostic_from=diagnostic_from)
    try:
        return run_case(case, corpus, criteria, condition=condition, model_name=model_name,
                        model_config=model, output_dir=output_dir, client=client, demo=False)
    finally:
        client.close()
