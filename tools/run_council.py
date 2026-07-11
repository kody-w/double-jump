#!/usr/bin/env python3
"""Run one exact-eight strategy council through the authenticated Copilot CLI."""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.brainstem import BrainstemError, CopilotCLIClient  # noqa: E402
from harness.council import CouncilConsensusError, repository_snapshot, run_council, write_receipt  # noqa: E402
from harness.policy import PolicyViolation, new_budget  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="max")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--completed", action="append", default=[])
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--policy")
    args = parser.parse_args()
    snapshot = repository_snapshot(ROOT)
    if args.snapshot_only:
        print(json.dumps(snapshot, indent=2))
        return 0
    completed = set(args.completed)
    index_path = os.path.join(ROOT, "council", "index.json")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as handle:
            index = json.load(handle)
        for cycle in index.get("cycles", []):
            completed.update(cycle.get("top_three") or [])
    provider = CopilotCLIClient(args.model, args.effort, args.timeout)
    budget = new_budget(args.policy) if args.policy else new_budget()
    try:
        provider.health()
        receipt = run_council(provider, snapshot, sorted(completed), budget=budget)
        path = write_receipt(ROOT, receipt)
    except CouncilConsensusError as exc:
        path = write_receipt(ROOT, exc.receipt)
        print(json.dumps({
            "status": "insufficient_consensus",
            "error": str(exc),
            "supported": exc.receipt["top_three"],
            "receipt": os.path.relpath(path, ROOT),
        }, indent=2))
        return 1
    except PolicyViolation as exc:
        print(json.dumps(exc.as_dict()))
        return 1
    except (BrainstemError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({
        "status": "complete",
        "cycle_id": receipt["cycle_id"],
        "top_three": receipt["top_three"],
        "receipt": os.path.relpath(path, ROOT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
