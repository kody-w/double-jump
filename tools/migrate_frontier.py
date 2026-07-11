#!/usr/bin/env python3
"""One-time, idempotent migration from warehouse observations to active lineages."""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.store import accept_jump, load_state, save_state  # noqa: E402
from harness.strength import strength  # noqa: E402

WAREHOUSE = os.path.join(ROOT, "warehouse", "moments.json")


def _base(title):
    return (title or "").split(" · ")[0]


def main():
    with open(WAREHOUSE, encoding="utf-8") as handle:
        document = json.load(handle)
    observations = document.get("moments", document if isinstance(document, list) else [])
    observed_count = len(observations)
    for revision in ("HEAD", "HEAD^"):
        try:
            original = subprocess.check_output(
                ["git", "show", f"{revision}:warehouse/moments.json"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            original_document = json.loads(original)
            original_moments = original_document.get(
                "moments",
                original_document if isinstance(original_document, list) else [],
            )
            observed_count = max(observed_count, len(original_moments))
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            pass
    state = load_state(WAREHOUSE)
    before_events = len(state.events)

    if not state.events:
        by_base = {}
        children = []
        for moment in state.moments:
            by_base.setdefault(_base(moment.get("t")), []).append(moment)
            if "double-jumped" in (moment.get("t") or ""):
                children.append(moment)
        for child in children:
            parents = [
                moment for moment in by_base.get(_base(child.get("t")), [])
                if moment is not child and "double-jumped" not in (moment.get("t") or "")
            ]
            if not parents:
                continue
            parent = min(parents, key=strength)
            alternatives = sorted(
                strength(moment)
                for moment in state.active_moments
                if moment is not parent and moment is not child
            )
            second = alternatives[0] if alternatives else strength(parent)
            bar = max(strength(parent) + 0.05, second)
            if strength(child) < bar:
                continue
            accept_jump(
                state,
                parent,
                child,
                bar,
                improver="legacy-brainstem",
                rationale="Migrated from the witnessed first double jump.",
                created_at="2026-06-21T21:30:00+00:00",
                allow_existing_child=True,
            )

    observed_count = max(observed_count, int(state.meta.get("legacy_observations") or 0))
    accepted_children = {
        event["child"] for event in state.events
        if event.get("type") == "accepted_jump"
    }
    state.meta.update({
        "legacy_observations": observed_count,
        "duplicate_observations_removed": observed_count - len(state.moments),
        "migration": "frontier-v1",
        "roots": sorted(set(state.by_id) - accepted_children),
    })
    changed = save_state(state)
    print(json.dumps({
        "status": "migrated" if changed else "current",
        "observations": observed_count,
        "artifacts": len(state.moments),
        "duplicates_removed": observed_count - len(state.moments),
        "events_added": len(state.events) - before_events,
        "active": len(state.active_moments),
        "floor": min(map(strength, state.active_moments)) if state.active_moments else None,
    }, indent=2))


if __name__ == "__main__":
    main()
