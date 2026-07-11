#!/usr/bin/env python3
"""Build the replay-verifiable lineage projection used by static clients."""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.store import load_state  # noqa: E402
from harness.strength import FITNESS_V1, FITNESS_V2, serialized_components, strength  # noqa: E402
from harness.validation import moment_id  # noqa: E402
from harness.diversity import archive_document, descriptor, niche  # noqa: E402

OUTPUT = os.path.join(ROOT, "warehouse", "lineages.json")


def build_document():
    state = load_state()
    parents, children, receipts = {}, {}, {}
    for event in state.events:
        if event["type"] != "accepted_jump":
            continue
        parents[event["child"]] = event["parent"]
        children.setdefault(event["parent"], []).append(event["child"])
        receipts[event["child"]] = event

    def depth(identifier):
        seen, current, count = set(), identifier, 0
        while current in parents:
            if current in seen:
                raise ValueError("lineage cycle detected")
            seen.add(current)
            current = parents[current]
            count += 1
        return count

    active = state.active_ids
    entries = []
    for identifier, moment in sorted(state.by_id.items()):
        event = receipts.get(identifier)
        entries.append({
            "id": identifier,
            "title": moment["t"],
            "author": moment["a"],
            "biome": moment["b"],
            "strength": strength(moment),
            "fitness": {
                FITNESS_V1: strength(moment, FITNESS_V1),
                FITNESS_V2: strength(moment, FITNESS_V2),
            },
            "components": serialized_components(moment),
            "active": identifier in active,
            "niche": niche(moment, FITNESS_V1),
            "descriptor": descriptor(moment, FITNESS_V1),
            "parent": parents.get(identifier),
            "children": sorted(children.get(identifier, [])),
            "depth": depth(identifier),
            "receipt": None if event is None else {
                "id": event["id"],
                "hash": event["hash"],
                "from": event["from"],
                "to": event["to"],
                "bar": event["bar"],
                "improver": event["improver"],
                "rationale": event["rationale"],
                "provenance": event.get("provenance") or {},
                "created_at": event["created_at"],
            },
        })
    return {
        "schema": "double-jump-lineages/1.0",
        "frontier_revision": state.revision,
        "event_head": state.events[-1]["hash"] if state.events else None,
        "artifacts": len(entries),
        "active": len(active),
        "quality_diversity": archive_document(state.active_moments, FITNESS_V1),
        "entries": entries,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = build_document()
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    old = open(OUTPUT, encoding="utf-8").read() if os.path.exists(OUTPUT) else None
    changed = old != text
    if changed and not args.check:
        with open(OUTPUT, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(json.dumps({"lineages": len(document["entries"]), "changed": changed}))
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
