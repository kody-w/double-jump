#!/usr/bin/env python3
"""Replay and verify every evolution receipt and generated projection."""

import json
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.store import load_state  # noqa: E402
from harness.strength import strength  # noqa: E402


def main():
    try:
        state = load_state()
        active = state.active_moments
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}))
        return 1
    manifest_path = os.path.join(ROOT, "warehouse", "build-manifest.json")
    manifest_status = "absent"
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        if manifest.get("frontier_revision") != state.revision:
            print(json.dumps({"status": "invalid", "error": "build manifest revision is stale"}))
            return 1
        for relative, expected in manifest.get("files", {}).items():
            path = os.path.join(ROOT, relative)
            if not os.path.exists(path):
                print(json.dumps({"status": "invalid", "error": f"manifest file missing: {relative}"}))
                return 1
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            if expected != "sha256:" + digest:
                print(json.dumps({"status": "invalid", "error": f"manifest hash mismatch: {relative}"}))
                return 1
        manifest_status = "verified"
    print(json.dumps({
        "status": "verified",
        "events": len(state.events),
        "head": state.events[-1]["hash"] if state.events else None,
        "artifacts": len(state.moments),
        "active": len(active),
        "floor": min(map(strength, active)) if active else None,
        "revision": state.revision,
        "build_manifest": manifest_status,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
