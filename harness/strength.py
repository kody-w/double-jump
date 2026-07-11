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
FITNESS_V1 = "double-jump-strength/1.0"
FITNESS_V2 = "double-jump-strength/2.0"
FITNESS_VERSIONS = (FITNESS_V1, FITNESS_V2)


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


def _components_v1(m):
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


def _components_v2(m):
    """A balance-seeking profile that resists keyframe stuffing and saturated extremes."""
    base = _components_v1(m)
    frames = _expand(m)
    keyframes = _sorted(m.get("k"))
    effective = 1
    for index in range(1, len(keyframes)):
        if _key(keyframes[index]) != _key(keyframes[index - 1]):
            effective += 1
    glow = base["glow"]
    spike = base["spike"]
    def clipping_fraction(frame):
        clipped = sum(
            frame.get(field, 0) <= 0.01 or frame.get(field, 0) >= 0.99
            for field in LIN
        )
        clipped += sum(abs(frame.get(field, 0)) >= 0.99 for field in DRIFT)
        return clipped / len(LIN + DRIFT)

    frame_clipping = _mean([clipping_fraction(frame) for frame in frames])
    keyframe_clipping = _mean([clipping_fraction(frame) for frame in keyframes])
    clipping = max(frame_clipping, keyframe_clipping)
    return {
        **base,
        "effective_articulation": min(effective / 8.0, 1.0),
        "glow_balance": max(0.0, 1 - abs(glow - 0.62) / 0.62),
        "spike_balance": max(0.0, 1 - abs(spike - 0.42) / 0.58),
        "smoothness": max(0.0, 1 - base["jerk"]),
        "clipping_penalty": min(clipping * 0.55, 0.55),
    }


def components(m, version=FITNESS_V1):
    if version in ("v1", FITNESS_V1):
        return _components_v1(m)
    if version in ("v2", FITNESS_V2):
        return _components_v2(m)
    raise ValueError(f"unknown fitness version: {version}")


def serialized_components(m, version=FITNESS_V1):
    """Stable generated-artifact representation across Python versions/platforms."""
    return {
        key: round(value, 10) if isinstance(value, float) else value
        for key, value in components(m, version).items()
    }


def strength(m, version=FITNESS_V1):
    """A single fitness scalar in [0,1]. Higher = stronger (more alive, articulated, dynamic)."""
    c = components(m, version)
    if version in ("v1", FITNESS_V1):
        raw = sum(_W[k] * c[k] for k in _W)
    elif version in ("v2", FITNESS_V2):
        axes = (
            c["effective_articulation"],
            c["motion"],
            c["glow_balance"],
            c["spike_balance"],
            c["variance"],
        )
        raw = (
            0.24 * axes[0]
            + 0.24 * axes[1]
            + 0.16 * axes[2]
            + 0.12 * axes[3]
            + 0.14 * axes[4]
            + 0.10 * c["smoothness"]
        )
        quality_floor = min(axes)
        raw = raw * (0.75 + 0.25 * quality_floor) - c["clipping_penalty"]
    else:
        raise ValueError(f"unknown fitness version: {version}")
    return round(max(0.0, min(1.0, c["vitality"] * raw)), 4)


def rank(moments, version=FITNESS_V1):
    """Return moments annotated with strength, sorted WEAKEST first."""
    out = [dict(m, _strength=strength(m, version)) for m in moments]
    out.sort(key=lambda m: m["_strength"])
    return out


def weakest(moments, version=FITNESS_V1):
    return rank(moments, version)[0] if moments else None
