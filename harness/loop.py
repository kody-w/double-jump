"""
loop.py — the double-jump harness: a generic, git-as-harness autonomous improvement loop.

The pattern (domain-agnostic):

    candidates()  ->  strength(x)  ->  pick the WEAKEST  ->  improve() until it clears the weakest
    by a MARGIN (the "double jump": don't just edge past it, leapfrog it)  ->  submit()  ->  repeat.

Git is the harness: every accepted improvement is an append-only commit, so the repo's history *is* the
record of the population getting better over time. Nothing is ever rewritten.

A `Domain` plugs three things into the loop: how to read candidates, how to score one, how to improve one,
and how to submit the result. `MomentDomain` (below) is the concrete domain over a warehouse of Moments.

CLI:  python3 -m harness.loop --rounds 1            # improve the weakest, append to the warehouse
      python3 -m harness.loop --triple-jump        # run one triple-jump tournament
"""
import argparse
import json
import os

from .moment import mint, improve
from .strength import strength, rank, weakest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAREHOUSE = os.path.join(ROOT, "warehouse", "moments.json")
MARGIN = 0.05            # a "double jump" must clear the weakest by at least this much
MAX_TRIES = 8           # escalate the boost until the margin is cleared


# ── the generic loop ─────────────────────────────────────────────────────────

def double_jump(candidates, improve_fn, strength_fn=strength, margin=MARGIN, max_tries=MAX_TRIES):
    """Find the weakest candidate and produce an improvement that clears it by `margin`.

    Returns {target, improved, from, to, margin, tries} or raises if no candidates."""
    ranked = sorted(candidates, key=strength_fn)
    if not ranked:
        raise ValueError("no candidates to improve")
    target = ranked[0]
    s_target = strength_fn(target)
    second = strength_fn(ranked[1]) if len(ranked) > 1 else s_target
    # a *double* jump clears the weakest AND at least reaches the next rung up — leapfrog, don't edge.
    bar = max(s_target + margin, second)
    best = None
    for boost in range(1, max_tries + 1):
        cand = improve_fn(target, boost=boost, seed=boost)
        if strength_fn(cand) >= bar and (best is None or strength_fn(cand) > strength_fn(best)):
            best = cand
            break
        best = cand if best is None or strength_fn(cand) > strength_fn(best) else best
    return {
        "target": target,
        "improved": best,
        "from": round(s_target, 4),
        "to": round(strength_fn(best), 4),
        "bar": round(bar, 4),
        "cleared": strength_fn(best) >= bar,
    }


def triple_jump(candidates, improve_fn, strength_fn=strength):
    """A three-round elimination: improve the weakest, reinsert, repeat 3x. The final improved organism
    is the champion that 'won the triple jump'. Houses the original triple-jump tournament idea."""
    pool = [dict(m) for m in candidates]
    history = []
    champion = None
    for rnd in range(1, 4):
        r = double_jump(pool, improve_fn, strength_fn)
        champ = dict(r["improved"])
        champ["t"] = f"{r['target'].get('t', 'Moment').split(' · ')[0]} · won the triple jump"
        history.append({"round": rnd, "from": r["from"], "to": r["to"]})
        # the improved organism replaces the weakest in the pool for the next hop
        pool = [m for m in pool if m is not r["target"]] + [champ]
        champion = champ
    return {"champion": champion, "rounds": history, "strength": round(strength_fn(champion), 4)}


# ── the Moment domain ────────────────────────────────────────────────────────

def load_warehouse(path=WAREHOUSE):
    if os.path.exists(path):
        d = json.load(open(path))
        return d.get("moments", d if isinstance(d, list) else [])
    return []


def save_warehouse(moments, path=WAREHOUSE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # idempotent stable-write (the build.py convention): only real changes touch disk.
    new = json.dumps({"moments": moments}, indent=2) + "\n"
    old = open(path).read() if os.path.exists(path) else None
    if new != old:
        open(path, "w").write(new)
        return True
    return False


def run(rounds=1, path=WAREHOUSE):
    moments = load_warehouse(path) or [mint(seed=0, n=2, title="Seed", author="@time")]
    log = []
    for _ in range(rounds):
        r = double_jump(moments, improve)
        moments.append(r["improved"])
        log.append({"target": r["target"].get("t"), "from": r["from"], "to": r["to"],
                    "cleared": r["cleared"], "new": r["improved"].get("t")})
    changed = save_warehouse(moments, path)
    return {"rounds": rounds, "log": log, "warehouse": len(moments), "changed": changed}


def main():
    ap = argparse.ArgumentParser(description="double-jump harness loop")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--triple-jump", action="store_true")
    ap.add_argument("--path", default=WAREHOUSE)
    a = ap.parse_args()
    if a.triple_jump:
        res = triple_jump(load_warehouse(a.path) or [mint(seed=1)], improve)
        save_warehouse(load_warehouse(a.path) + [res["champion"]], a.path)
        print(json.dumps({"triple_jump": res["rounds"], "champion": res["champion"]["t"],
                          "strength": res["strength"]}, indent=2))
    else:
        print(json.dumps(run(a.rounds, a.path), indent=2))


if __name__ == "__main__":
    main()
