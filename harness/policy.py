"""Versioned, deterministic autonomy authorization and run budgets."""

from dataclasses import dataclass, field
import hashlib
import json
import os
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_POLICY = os.path.join(ROOT, "autonomy-policy.json")
SCHEMA = "double-jump-autonomy-policy/1.0"


class PolicyViolation(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

    def as_dict(self):
        return {"status": "policy_rejected", "code": self.code, "error": str(self)}


def load_policy(path=DEFAULT_POLICY):
    with open(path, encoding="utf-8") as handle:
        policy = json.load(handle)
    if policy.get("schema") != SCHEMA:
        raise PolicyViolation("bad_policy_schema", f"policy must use {SCHEMA}")
    limits = policy.get("limits")
    effects = policy.get("side_effects")
    if not isinstance(limits, dict) or not isinstance(effects, dict):
        raise PolicyViolation("bad_policy", "policy requires limits and side_effects objects")
    for key in ("max_rounds", "max_provider_calls", "max_council_calls", "max_run_seconds", "max_response_bytes"):
        value = limits.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PolicyViolation("bad_policy_limit", f"{key} must be a positive integer")
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return policy, "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class RunBudget:
    policy: dict
    policy_digest: str
    started: float = field(default_factory=time.monotonic)
    provider_calls: int = 0
    council_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _deadline_check(self):
        if time.monotonic() - self.started > self.policy["limits"]["max_run_seconds"]:
            raise PolicyViolation("run_deadline", "autonomous run exceeded its wall-clock budget")

    def authorize_rounds(self, rounds):
        if isinstance(rounds, bool) or not isinstance(rounds, int) or not 0 <= rounds <= self.policy["limits"]["max_rounds"]:
            raise PolicyViolation("round_budget", f"rounds must be in [0, {self.policy['limits']['max_rounds']}]")
        self._deadline_check()

    def consume_provider(self, count=1):
        with self._lock:
            self._deadline_check()
            if self.provider_calls + count > self.policy["limits"]["max_provider_calls"]:
                raise PolicyViolation("provider_budget", "provider call budget exhausted")
            self.provider_calls += count

    def consume_council(self, count=1):
        with self._lock:
            self._deadline_check()
            if self.council_calls + count > self.policy["limits"]["max_council_calls"]:
                raise PolicyViolation("council_budget", "council call budget exhausted")
            self.council_calls += count

    def authorize_side_effect(self, name, explicit=False):
        decision = self.policy["side_effects"].get(name, False)
        if decision is True or (decision == "explicit" and explicit):
            return True
        raise PolicyViolation("side_effect_denied", f"policy denied side effect: {name}")

    def receipt(self):
        return {
            "policy": self.policy_digest,
            "provider_calls": self.provider_calls,
            "council_calls": self.council_calls,
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
        }


def new_budget(path=DEFAULT_POLICY):
    policy, digest = load_policy(path)
    return RunBudget(policy, digest)
