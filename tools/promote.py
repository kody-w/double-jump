#!/usr/bin/env python3
"""
promote.py — the cubby's reach-up to the global Moment platform (SANDBOX.md §3b).

The double-jump twin works in its sandbox warehouse. To make a proven improvement show *globally* it
reaches up the polite way: a **pull request** to kody-w/rapp-commons hologram/moments.json — never a direct
push to that repo's main. Only genuine improvements (double-jumped organisms) are promoted; raw seeds stay
in the sandbox.

It branches a FRESH clone of the real platform's main (not the operator's local clone), appends the
selected Moments (deduped by token), pushes a branch, and opens a PR.

Usage:
  python3 tools/promote.py                 # dry-run: list what would be promoted
  python3 tools/promote.py --apply         # open a PR to kody-w/rapp-commons
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.moment import encode_token            # noqa: E402
from harness.store import load_state                # noqa: E402
from harness.strength import strength              # noqa: E402
from harness.policy import PolicyViolation, new_budget  # noqa: E402

PLATFORM = "kody-w/rapp-commons"
FEED = "hologram/moments.json"
PLAYER = "https://kody-w.github.io/rapp-hologram/"
WAREHOUSE = os.path.join(ROOT, "warehouse", "moments.json")


def _run(args, cwd=None):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _load(path):
    d = json.load(open(path))
    return d.get("moments", d if isinstance(d, list) else [])


def select_improvements(state):
    """Select only children witnessed by accepted evolution receipts."""
    accepted = {
        event["child"] for event in state.events
        if event.get("type") == "accepted_jump"
    }
    return [moment for identifier, moment in state.by_id.items() if identifier in accepted]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually open the PR (default: dry-run)")
    ap.add_argument("--policy")
    a = ap.parse_args()

    candidates = select_improvements(load_state(WAREHOUSE))
    if not candidates:
        print(json.dumps({"status": "nothing", "reason": "no receipt-backed improvements in the sandbox"}))
        return 0
    summary = [{"title": m.get("t"), "strength": strength(m), "play": PLAYER + "?m=" + encode_token(m)}
               for m in candidates]

    if not a.apply:
        print(json.dumps({"status": "dry-run", "mode": "pr", "would_promote": len(candidates),
                          "selection": summary,
                          "note": "re-run with --apply to open a PR to " + PLATFORM}, indent=2))
        return 0
    try:
        budget = new_budget(a.policy) if a.policy else new_budget()
        budget.authorize_side_effect("promotion_pr", explicit=True)
    except PolicyViolation as exc:
        print(json.dumps(exc.as_dict()))
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        clone = os.path.join(tmp, "rapp-commons")
        rc, _, err = _run(["gh", "repo", "clone", PLATFORM, clone, "--", "--depth", "1"])
        if rc != 0:
            print(json.dumps({"status": "error", "stage": "clone", "error": err})); return 1

        feed_path = os.path.join(clone, FEED)
        feed = _load(feed_path)
        have = {encode_token(m) for m in feed}
        added = [m for m in candidates if encode_token(m) not in have]
        if not added:
            print(json.dumps({"status": "noop", "reason": "all selected improvements already on the global feed"}))
            return 0
        feed.extend(added)
        # preserve the feed's on-disk format: the warehouse files are minified single-line (the
        # git-scraping convention), so a compact write keeps the diff to one line, not a full reformat.
        orig = open(feed_path).read()
        minified = "\n" not in orig.strip()
        with open(feed_path, "w") as fh:
            if minified:
                fh.write(json.dumps({"moments": feed}, separators=(",", ":"), ensure_ascii=False))
            else:
                json.dump({"moments": feed}, fh, indent=2, ensure_ascii=False)

        _run(["git", "config", "user.name", "double-jump-twin"], cwd=clone)
        _run(["git", "config", "user.email", "actions@github.com"], cwd=clone)
        titles = ", ".join(m.get("t", "Moment") for m in added)
        branch = f"promote/double-jump-{int(time.time())}"
        _run(["git", "checkout", "-b", branch], cwd=clone)
        _run(["git", "add", FEED], cwd=clone)
        _run(["git", "commit", "-m", f"promote: {len(added)} double-jump improvement(s) -> the global feed"], cwd=clone)
        rc, _, err = _run(["git", "push", "-u", "origin", branch], cwd=clone)
        if rc != 0:
            print(json.dumps({"status": "error", "stage": "push", "error": err})); return 1

        body = ("The **double-jump twin** reaching up from its sandbox cubby to promote proven improvements "
                "to the global feed.\n\n**Promoted (improvements only):**\n" +
                "\n".join(f"- **{m.get('t')}** · strength {strength(m)} · "
                          f"[play]({PLAYER}?m={encode_token(m)})" for m in added) +
                "\n\n_Selected by the `double-jumped` marker; deduped against the current feed. "
                "Reach-up is by PR, never a direct push to `main` (see double-jump SANDBOX.md §3b)._")
        rc, out, err = _run(["gh", "pr", "create", "--repo", PLATFORM, "--base", "main", "--head", branch,
                             "--title", f"promote: {len(added)} double-jump improvement(s)", "--body", body], cwd=clone)
        if rc != 0:
            print(json.dumps({"status": "pushed_no_pr", "branch": branch, "error": err})); return 1
        print(json.dumps({"status": "pr_opened", "mode": "pr", "added": len(added),
                          "titles": titles, "pr_url": out.split()[-1] if out else "", "branch": branch}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
