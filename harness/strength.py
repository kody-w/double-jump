"""
strength.py — the fitness function the double-jump harness ranks by.

Grounded in the rapp-hologram engine's own canonical metrics:

  - vitality (homeostasis.js):  vitality = max(0, 1 - stress/STRESS_LIMIT);  alive iff stress < 12.
    A fresh/consistent Moment has stress 0 → vitality 1. Death gates strength to 0.
  - motion / glow / spike ENERGY (fingerprint.js): the ~40-D descriptor rewards path length (motion),
    jerk, mean glow, mean spikes — sampled across the whole 100-frame trajectory.
  - generation: the number of keyframes (articulation). "Stillness" (k=2, flat) is weak; a rich,
    dynamic multi-keyframe organism is strong.

strength(m) ∈ [0,1] combines vitality-gated articulation + motion + glow + spike + variance energy, so
"weakest" = least alive / least articulated / least dynamic. The double-jump loop improves the weakest
until it clears that bar by a margin.
"""
from .moment import LIN, DRIFT

STRESS_LIMIT = 12          # matches homeostasis.js
N = 100                    # frames sampled


def _sorted(k):
    return sorted(k or [], key=lambda f: f["at"])


def _sample_at(s, at):
    if not s:
        return {}
    if at <= s[0]["at"]:
        return s[0]
    if at >= s[-1]["at"]:
        return s[-1]
    for i in range(len(s) - 1):
        a, b = s[i], s[i + 1]
        if a["at"] <= at <= b["at"]:
            t = (at - a["at"]) / ((b["at"] - a["at"]) or 1)
            o = {}
            for f in LIN + DRIFT:
                o[f] = a.get(f, 0) + (b.get(f, 0) - a.get(f, 0)) * t
            return o
    return s[-1]


def _expand(m):
    s = _sorted(m.get("k"))
    return [_sample_at(s, i / (N - 1) * 99) for i in range(N)]


def vitality(m):
    """Stress rises when a keyframe would rewrite a settled one (a contradiction). For well-formed,
    monotonic-`at` genomes stress is 0 -> vitality 1. Duplicate / backward `at` collisions add stress."""
    s = _sorted(m.get("k"))
    stress = 0
    seen = {}
    for f in s:
        at = f["at"]
        if at in seen and seen[at] != _key(f):
            stress += 1                      # two different frames claim one slot — a contradiction
        seen[at] = _key(f)
    alive = stress < STRESS_LIMIT
    return max(0.0, 1 - stress / STRESS_LIMIT) if alive else 0.0


def _key(f):
    return tuple(round(f.get(k, 0), 4) for k in LIN + DRIFT)


def _mean(a):
    return sum(a) / (len(a) or 1)


def _std(a):
    m = _mean(a)
    return (_mean([(x - m) ** 2 for x in a])) ** 0.5


def components(m):
    fr = _expand(m)
    gen = len(_sorted(m.get("k")))
    path = sum(((fr[i]["x"] - fr[i - 1]["x"]) ** 2 + (fr[i]["z"] - fr[i - 1]["z"]) ** 2) ** 0.5
               for i in range(1, len(fr)))
    jerk = sum(abs(fr[i]["s"] - 2 * fr[i - 1]["s"] + fr[i - 2]["s"]) for i in range(2, len(fr)))
    glow = _mean([f["g"] for f in fr])
    spike = _mean([f["p"] for f in fr])
    var = _mean([_std([f[k] for f in fr]) for k in LIN])
    return {
        "generation": gen,
        "articulation": min(gen / 8.0, 1.0),
        "motion": min(path / 5.0, 1.0),
        "jerk": min(jerk / 2.0, 1.0),
        "glow": glow,
        "spike": spike,
        "variance": min(var * 3.0, 1.0),
        "vitality": vitality(m),
    }


# weights sum to 1 over the five energy/articulation terms; vitality is a multiplicative gate.
_W = {"articulation": 0.30, "motion": 0.25, "jerk": 0.10, "glow": 0.15, "spike": 0.08, "variance": 0.12}


def strength(m):
    """A single fitness scalar in [0,1]. Higher = stronger (more alive, articulated, dynamic)."""
    c = components(m)
    raw = sum(_W[k] * c[k] for k in _W)
    return round(c["vitality"] * raw, 4)


def rank(moments):
    """Return moments annotated with strength, sorted WEAKEST first."""
    out = [dict(m, _strength=strength(m)) for m in moments]
    out.sort(key=lambda m: m["_strength"])
    return out


def weakest(moments):
    return rank(moments)[0] if moments else None
