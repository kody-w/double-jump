"""
arena.py — the competition layer that turns a solo improver into a multiplayer network.

Many twins (authors, each a rappid) submit Moments into one shared arena. They are ranked on a single
`strength` leaderboard. The strongest is the reigning **champion** (king-of-the-hill): to take the crown a
twin must submit a Moment that beats the current champion. The reigning champion is what gets promoted up
to the global platform.

Pure, deterministic, dependency-free — the same discipline as the rest of the harness.
"""
import random

from .moment import BIOMES, _clamp, _value_at
from .strength import strength


def leaderboard(moments):
    """All Moments ranked STRONGEST first, each annotated with strength + author (the arena floor)."""
    rows = [dict(m, _strength=strength(m)) for m in moments]
    rows.sort(key=lambda m: m["_strength"], reverse=True)
    return rows


def champion(moments):
    """The reigning champion = the single strongest Moment."""
    lb = leaderboard(moments)
    return lb[0] if lb else None


def standings(moments):
    """Per-twin standings: each author's best Moment + how many they've entered, ranked by their best."""
    by = {}
    for m in moments:
        a = m.get("a") or "@anon"
        s = strength(m)
        cur = by.get(a)
        if cur is None or s > cur["best_strength"]:
            by[a] = {"twin": a, "best_strength": s, "best_title": m.get("t"), "entries": 0}
    for m in moments:
        a = m.get("a") or "@anon"
        by[a]["entries"] += 1
    out = sorted(by.values(), key=lambda r: r["best_strength"], reverse=True)
    for i, r in enumerate(out):
        r["rank"] = i + 1
    return out


def beats(contender, current_champion, margin=0.0):
    """King-of-the-hill rule: a contender takes the crown only by clearing the champion (by `margin`)."""
    if current_champion is None:
        return True
    return strength(contender) >= strength(current_champion) + margin


def _main():
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    wh = os.path.join(os.path.dirname(here), "warehouse", "moments.json")
    moments = json.load(open(wh))["moments"]
    champ = champion(moments)
    print(f"ARENA — {len(moments)} organisms · champion: {champ['t']} ({strength(champ)})\n")
    print("per-twin standings:")
    for r in standings(moments):
        print(f"  #{r['rank']} {r['twin']:14} best {r['best_strength']:.4f}  ({r['entries']} entries)")
    print("\nleaderboard:")
    for i, m in enumerate(leaderboard(moments)):
        crown = "👑" if i == 0 else f"#{i+1}"
        print(f"  {crown:>3} {m['_strength']:.4f}  {m['t']}  ({m.get('a')})")


if __name__ == "__main__":
    _main()


def forge(beat=0.0, seed=None, author="@challenger", biome=None, title=None, max_tries=24):
    """Mint a fresh, high-energy contender that aims to top the leaderboard — the 'attack the ceiling'
    strategy (contrast to double-jump's 'raise the floor'). Returns the strongest of several tries that
    clears `beat`; falls back to the strongest tried."""
    best = None
    for t in range(max_tries):
        rng = random.Random((seed or 0) * 1000 + t)
        n = rng.randint(6, 8)
        ats = [round(i / (n - 1) * 99) for i in range(n)]
        k = []
        for i, at in enumerate(ats):
            # alternate drift to the extremes for high motion; high glow/spike for energy; varied hue/size
            sgn = 1 if i % 2 == 0 else -1
            k.append({
                "at": int(at),
                "s": round(rng.uniform(0.2, 0.95), 3),
                "l": round(rng.uniform(0.2, 0.8), 3),
                "p": round(rng.uniform(0.4, 0.9), 3),
                "g": round(rng.uniform(0.6, 0.95), 3),
                "h": round(rng.uniform(0, 360), 1),
                "x": round(_clamp(sgn * rng.uniform(0.5, 0.95), -1, 1), 3),
                "z": round(_clamp(-sgn * rng.uniform(0.5, 0.95), -1, 1), 3),
            })
        m = {"v": 1, "t": title or f"Contender {(seed or 0)}-{t}", "a": author,
             "b": biome or rng.choice(BIOMES), "k": k}
        if best is None or strength(m) > strength(best):
            best = m
        if strength(m) >= beat:
            return m
    return best
