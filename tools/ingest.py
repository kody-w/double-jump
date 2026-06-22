#!/usr/bin/env python3
"""
ingest.py — the static-API CRUD executor (issue-ops).

GitHub Pages can't write, so a submission is a GitHub **Issue** (the write endpoint). This tool is what
the `ingest` workflow runs on each `moment-submit` issue: it parses the issue body, decodes the Moment
share token, verifies it, and applies the CRUD op to the static warehouse (`warehouse/moments.json`),
append-only and idempotent (the build.py stable-write convention — only real changes touch disk).

  op = create | update | delete   (read = report only)

Body source (first hit wins): argv[1] file path, $ISSUE_BODY, or stdin. Prints a JSON result the
workflow posts back as a comment.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.moment import decode_token, encode_token          # noqa: E402
from harness.strength import strength                           # noqa: E402

WAREHOUSE = os.path.join(ROOT, "warehouse", "moments.json")
PLAYER_BASE = "https://kody-w.github.io/rapp-hologram/"


def _read_body():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return open(sys.argv[1]).read()
    if os.environ.get("ISSUE_BODY"):
        return os.environ["ISSUE_BODY"]
    return sys.stdin.read()


def _sections(body):
    """Split a GitHub issue-form body into { lowercased-heading: text } by `### heading` markers."""
    out, cur, buf = {}, None, []
    for line in body.splitlines():
        m = re.match(r"^\s*#{2,4}\s+(.+?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1).strip().lower(), []
        else:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def _strip_fence(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _find_token(sections, body):
    if "token" in sections and sections["token"]:
        return _strip_fence(sections["token"]).split()[0]
    # fallback: the longest base64url-looking run in the body
    cands = re.findall(r"[A-Za-z0-9_\-]{40,}", body)
    return max(cands, key=len) if cands else None


def _load():
    if os.path.exists(WAREHOUSE):
        d = json.load(open(WAREHOUSE))
        return d.get("moments", d if isinstance(d, list) else [])
    return []


def _save(moments):
    os.makedirs(os.path.dirname(WAREHOUSE), exist_ok=True)
    new = json.dumps({"moments": moments}, indent=2) + "\n"
    old = open(WAREHOUSE).read() if os.path.exists(WAREHOUSE) else None
    if new != old:
        open(WAREHOUSE, "w").write(new)
        return True
    return False


def main():
    body = _read_body()
    sec = _sections(body)
    op = (_strip_fence(sec.get("op", "create")) or "create").split()[0].lower()
    if op not in ("create", "update", "delete", "read"):
        op = "create"

    token = _find_token(sec, body)
    if not token:
        print(json.dumps({"status": "error", "error": "no Moment token found in the issue"}))
        return 1
    try:
        m = decode_token(token)
        assert isinstance(m, dict) and m.get("k"), "not a Moment record"
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"bad token: {e}"}))
        return 1

    s = strength(m)
    if s <= 0:
        print(json.dumps({"status": "rejected", "error": "Moment is not alive (strength 0)", "title": m.get("t")}))
        return 1

    moments = _load()
    tokens = [encode_token(x) for x in moments]
    tok = encode_token(m)
    result = {"op": op, "title": m.get("t"), "author": m.get("a"), "biome": m.get("b"),
              "keyframes": len(m.get("k", [])), "strength": s,
              "play_url": PLAYER_BASE + "?m=" + tok}

    if op == "read":
        result["status"] = "ok"
        result["present"] = tok in tokens
    elif op == "delete":
        before = len(moments)
        moments = [x for i, x in enumerate(moments) if tokens[i] != tok]
        changed = _save(moments)
        result["status"] = "deleted" if len(moments) < before else "absent"
        result["changed"] = changed
    else:  # create / update — upsert (append-only growth; identical re-submit is a no-op)
        if tok in tokens:
            result["status"] = "duplicate"
            result["changed"] = False
        else:
            moments.append(m)
            result["changed"] = _save(moments)
            result["status"] = "created"
    result["warehouse"] = len(moments)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
