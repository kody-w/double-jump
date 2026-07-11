"""
moment.py — mint, encode, and improve RAPP Moments (the unit the double-jump harness improves).

A Moment is a small record { v, t, a, b, k } where k is the genome: keyframes of a form
{ at, s, l, p, g, h, x, z } interpolated to 100 frames and played as a walkable hologram. This module
is the pure, deterministic, dependency-free Python side of the kody-w/rapp-moment standard:

  - encode_token(m)  -> base64url(JSON.stringify(m))   (matches rapp-hologram moment.js `encode`)
  - decode_token(t)  -> m
  - mint(seed=...)   -> a fresh valid Moment
  - improve(m, ...)  -> a richer Moment (more articulation / motion / glow) — the raw material for a "jump"

MVP: Moments are unsigned (matching the existing public warehouse). Signing (ECDSA P-256, byte-matching
the engine's verifier) is an additive follow-up — add `sig`/`pub` fields; never version the record.
"""
import base64
import json
import random

from .validation import decode_token as decode_validated_token
from .validation import validate_moment

BIOMES = ["savanna", "canyon", "forest", "volcanic", "void"]
LIN = ["s", "l", "p", "g"]          # 0..1 fields
DRIFT = ["x", "z"]                   # -1..1 drift


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def encode_token(m):
    """Canonical share token: base64url(compact-JSON), padding stripped. Matches moment.js encode()."""
    validate_moment(m)
    raw = json.dumps(m, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_token(token):
    return decode_validated_token(token)


def _frame(rng, at):
    f = {"at": int(at)}
    for k in LIN:
        f[k] = round(rng.uniform(0.05, 0.95), 3)
    f["h"] = round(rng.uniform(0, 360), 1)
    for k in DRIFT:
        f[k] = round(rng.uniform(-0.9, 0.9), 3)
    return f


def mint(seed=None, n=None, biome=None, title=None, author="@double-jump"):
    """Deterministically mint a fresh, valid Moment. `seed` makes it reproducible."""
    rng = random.Random(seed)
    n = n if n else rng.randint(2, 4)
    ats = [0] + sorted(rng.sample(range(1, 99), max(0, n - 2))) + [99] if n >= 2 else [0, 99]
    k = [_frame(rng, at) for at in ats]
    moment = {
        "v": 1,
        "t": title or f"Mint {rng.randint(1000, 9999)}",
        "a": author,
        "b": biome or rng.choice(BIOMES),
        "k": k,
    }
    return validate_moment(moment)


def _value_at(k, at):
    """Linear interpolation of a sorted keyframe list at frame `at` (hue interpolated circularly)."""
    s = sorted(k, key=lambda f: f["at"])
    if at <= s[0]["at"]:
        return dict(s[0])
    if at >= s[-1]["at"]:
        return dict(s[-1])
    for i in range(len(s) - 1):
        a, b = s[i], s[i + 1]
        if a["at"] <= at <= b["at"]:
            t = (at - a["at"]) / ((b["at"] - a["at"]) or 1)
            o = {"at": int(at)}
            for f in LIN + DRIFT:
                o[f] = round(a.get(f, 0) + (b.get(f, 0) - a.get(f, 0)) * t, 4)
            ha, hb = a.get("h", 0), b.get("h", 0)
            dd = ((hb - ha + 540) % 360) - 180
            o["h"] = round((ha + dd * t + 360) % 360, 2)
            return o
    return dict(s[-1])


def improve(m, boost=1, seed=None):
    """Return a richer variant of `m`: insert interpolated mid-keyframes and amplify motion/glow/spikes.

    This deepens articulation (more keyframes), motion (x/z drift), glow (g), and spikes (p) — the exact
    terms the strength function rewards — while staying within bounds and keeping at[0]=0, at[-1]=99.
    `boost` controls how aggressively to enrich (higher = stronger jump)."""
    validate_moment(m)
    rng = random.Random(seed)
    k = sorted((dict(f) for f in m.get("k", [])), key=lambda f: f["at"])
    if len(k) < 2:
        k = [_value_at(k or [{"at": 0, "s": 0.3, "l": 0.3, "p": 0.1, "g": 0.2, "h": 40, "x": 0, "z": 0}], 0),
             _value_at(k or [{"at": 99, "s": 0.4, "l": 0.3, "p": 0.1, "g": 0.3, "h": 60, "x": 0, "z": 0}], 99)]

    # 1) insert a midpoint keyframe in each of the `boost` largest gaps → more articulation
    for _ in range(boost):
        gaps = [(k[i + 1]["at"] - k[i]["at"], i) for i in range(len(k) - 1)]
        gaps.sort(reverse=True)
        if not gaps or gaps[0][0] < 2:
            break
        _, i = gaps[0]
        mid_at = (k[i]["at"] + k[i + 1]["at"]) // 2
        nf = _value_at(k, mid_at)
        # perturb the midpoint toward more energy (motion + glow + spikes), within bounds
        nf["x"] = round(_clamp(nf["x"] + rng.uniform(-0.5, 0.5), -1, 1), 3)
        nf["z"] = round(_clamp(nf["z"] + rng.uniform(-0.5, 0.5), -1, 1), 3)
        nf["g"] = round(_clamp(nf["g"] + rng.uniform(0.05, 0.25), 0, 1), 3)
        nf["p"] = round(_clamp(nf["p"] + rng.uniform(0.05, 0.25), 0, 1), 3)
        nf["h"] = round((nf["h"] + rng.uniform(20, 80)) % 360, 2)
        k = sorted(k + [nf], key=lambda f: f["at"])

    # 2) gently lift glow + spikes across all frames → richer organism
    amp = 0.06 * boost
    for f in k:
        f["g"] = round(_clamp(f.get("g", 0) + amp, 0, 1), 3)
        f["p"] = round(_clamp(f.get("p", 0) + amp * 0.7, 0, 1), 3)

    out = dict(m)
    out["k"] = k
    base_t = m.get("t", "Moment").split(" · ")[0]
    out["t"] = f"{base_t} · double-jumped"
    return validate_moment(out)


def draft_improvements(m):
    """Return three deterministic, non-persistent evolution choices for the player lab."""
    validate_moment(m)
    base_title = m["t"].split(" · ")[0]
    drafts = []

    motion = improve(m, boost=2, seed=101)
    for index, frame in enumerate(motion["k"]):
        direction = 1 if index % 2 == 0 else -1
        frame["x"] = round(_clamp(frame["x"] + direction * 0.28, -1, 1), 3)
        frame["z"] = round(_clamp(frame["z"] - direction * 0.24, -1, 1), 3)
    motion["t"] = f"{base_title} · motion draft"
    drafts.append(("motion", validate_moment(motion)))

    articulation = improve(m, boost=4, seed=202)
    for index, frame in enumerate(articulation["k"]):
        direction = 1 if index % 2 == 0 else -1
        frame["s"] = round(_clamp(frame["s"] + direction * 0.12, 0, 1), 3)
        frame["l"] = round(_clamp(frame["l"] - direction * 0.08, 0, 1), 3)
    articulation["t"] = f"{base_title} · articulation draft"
    drafts.append(("articulation", validate_moment(articulation)))

    radiance = improve(m, boost=2, seed=303)
    for index, frame in enumerate(radiance["k"]):
        frame["g"] = round(_clamp(frame["g"] + 0.14, 0, 1), 3)
        frame["p"] = round(_clamp(frame["p"] + 0.10, 0, 1), 3)
        frame["h"] = round((frame["h"] + 35 + index * 7) % 360, 2)
    radiance["t"] = f"{base_title} · radiance draft"
    drafts.append(("radiance", validate_moment(radiance)))

    return drafts
