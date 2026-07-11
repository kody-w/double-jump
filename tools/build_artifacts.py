#!/usr/bin/env python3
"""Materialize every static view from the active frontier."""

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "warehouse", "build-manifest.json")


def _run(args):
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"{args} failed")
    return json.loads(result.stdout)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _manifest(check=False):
    with open(os.path.join(ROOT, "cards.json"), encoding="utf-8") as handle:
        cards = json.load(handle)
    expected_resolve = {
        os.path.join(ROOT, "resolve", card_id.split("/")[-1] + ".json")
        for card_id in cards["cards"]
    }
    actual_resolve = set(glob.glob(os.path.join(ROOT, "resolve", "*.json")))
    extras = sorted(actual_resolve - expected_resolve)
    missing = sorted(expected_resolve - actual_resolve)
    if not check:
        for path in extras:
            os.unlink(path)
        actual_resolve -= set(extras)
    files = [
        os.path.join(ROOT, "cards.json"),
        os.path.join(ROOT, "seed-index.json"),
        os.path.join(ROOT, "warehouse", "frontier.json"),
        os.path.join(ROOT, "warehouse", "lineages.json"),
        *sorted(expected_resolve),
    ]
    absent = [path for path in files if not os.path.exists(path)]
    with open(os.path.join(ROOT, "warehouse", "frontier.json"), encoding="utf-8") as handle:
        frontier = json.load(handle)
    document = {
        "schema": "double-jump-build-manifest/1.0",
        "frontier_revision": frontier["revision"],
        "files": {
            os.path.relpath(path, ROOT): _sha256(path)
            for path in files if os.path.exists(path)
        },
    }
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as handle:
            old = handle.read()
    else:
        old = None
    changed = old != text
    if changed and not check:
        with open(MANIFEST, "w", encoding="utf-8") as handle:
            handle.write(text)
    return {
        "changed": changed,
        "missing": [os.path.relpath(path, ROOT) for path in missing + absent],
        "extra": [os.path.relpath(path, ROOT) for path in extras],
        "files": len(document["files"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    suffix = ["--check"] if args.check else []
    try:
        lineages = _run(["tools/build_lineages.py", *suffix])
        cards = _run(["tools/mint_cards.py", *suffix])
        resolved = _run(["tools/resolve_card.py", "--all", *suffix])
        manifest = _manifest(args.check)
        if args.check and (manifest["changed"] or manifest["missing"] or manifest["extra"]):
            raise RuntimeError("build manifest or generated file set is stale: " + json.dumps(manifest))
    except RuntimeError as exc:
        print(json.dumps({"status": "stale" if args.check else "error", "error": str(exc)}))
        return 1
    print(json.dumps({
        "status": "current" if args.check else "built",
        "lineages": lineages,
        "cards": cards,
        "resolve": resolved,
        "manifest": manifest,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
