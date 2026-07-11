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
from .strength import FITNESS_V1, FITNESS_V2, strength, rank, weakest
from .store import (
    EVOLUTION,
    WAREHOUSE,
    EvolutionState,
    accept_jump,
    load_state,
    save_state,
)
from .validation import moment_id
from .policy import PolicyViolation, new_budget

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    attempts = []
    for boost in range(1, max_tries + 1):
        cand = improve_fn(target, boost=boost, seed=boost)
        try:
            candidate_id = moment_id(cand)
        except (TypeError, ValueError):
            candidate_id = None
        attempts.append({
            "attempt": boost,
            "candidate_id": candidate_id,
            "strength": strength_fn(cand),
            "boost": boost,
            "seed": boost,
        })
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
        "attempts": attempts,
    }


def triple_jump(candidates, improve_fn, strength_fn=strength):
    """A three-round elimination: improve the weakest, reinsert, repeat 3x. The final improved organism
    is the champion that 'won the triple jump'. Houses the original triple-jump tournament idea."""
    pool = [dict(m) for m in candidates]
    history = []
    champion = None
    for rnd in range(1, 4):
        r = double_jump(pool, improve_fn, strength_fn)
        if not r["cleared"]:
            raise ValueError(f"triple jump round {rnd} did not clear its bar")
        champ = dict(r["improved"])
        champ["t"] = f"{r['target'].get('t', 'Moment').split(' · ')[0]} · won the triple jump"
        history.append({
            "round": rnd,
            "from": r["from"],
            "to": r["to"],
            "bar": r["bar"],
            "target": r["target"],
            "improved": champ,
        })
        # the improved organism replaces the weakest in the pool for the next hop
        pool = [m for m in pool if m is not r["target"]] + [champ]
        champion = champ
    return {"champion": champion, "rounds": history, "strength": round(strength_fn(champion), 4)}


# ── the Moment domain ────────────────────────────────────────────────────────

def load_warehouse(path=WAREHOUSE, active=True):
    state = load_state(path)
    return state.active_moments if active else state.moments


def save_warehouse(moments, path=WAREHOUSE):
    state = load_state(path)
    state.moments = list(moments)
    return save_state(state)


def run(rounds=1, path=WAREHOUSE, evolution_path=None, improver="deterministic",
        brainstem_url=None, brainstem_timeout=90, copilot_model="gpt-5.6-sol",
        copilot_effort="max", fitness_version=FITNESS_V1, policy_path=None,
        selection_policy="floor"):
    budget = new_budget(policy_path) if policy_path else new_budget()
    budget.authorize_rounds(rounds)
    state = load_state(path, evolution_path=evolution_path)
    if not state.moments:
        state.moments.append(mint(seed=0, n=2, title="Seed", author="@time"))
    log = []
    accepted = 0
    client = None
    if improver == "brainstem":
        from .brainstem import BrainstemClient
        client = BrainstemClient(brainstem_url or "http://127.0.0.1:7071", brainstem_timeout)
        client.health()
    elif improver == "copilot-cli":
        from .brainstem import CopilotCLIClient
        client = CopilotCLIClient(copilot_model, copilot_effort, max(brainstem_timeout, 300))
        client.health()
    elif improver != "deterministic":
        raise ValueError("improver must be deterministic, brainstem, or copilot-cli")

    for _ in range(rounds):
        active = state.active_moments
        diversity_decision = None
        candidates = active
        if selection_policy == "quality-diversity":
            from .diversity import archive
            candidates = list(archive(active, fitness_version).values())
        elif selection_policy != "floor":
            raise ValueError("selection_policy must be floor or quality-diversity")
        strength_fn = lambda moment: strength(moment, fitness_version)
        if improver in ("brainstem", "copilot-cli"):
            from .brainstem import brainstem_jump
            r = brainstem_jump(candidates, client, fitness_version=fitness_version, budget=budget)
        else:
            r = double_jump(candidates, improve, strength_fn=strength_fn)
        entry = {
            "target": r["target"].get("t"),
            "from": r["from"],
            "to": r["to"],
            "bar": r["bar"],
            "cleared": r["cleared"],
            "new": r["improved"].get("t"),
            "improver": improver,
            "fitness": fitness_version,
        }
        if not r["cleared"]:
            entry["status"] = "rejected"
            log.append(entry)
            break
        if selection_policy == "quality-diversity":
            from .diversity import admission
            diversity_decision = admission(
                r["target"],
                r["improved"],
                active,
                r["bar"],
                fitness_version,
            )
            entry["quality_diversity"] = diversity_decision
            if not diversity_decision["accepted"]:
                entry["status"] = "rejected_" + diversity_decision["reason"]
                log.append(entry)
                break
        changed, status = accept_jump(
            state,
            r["target"],
            r["improved"],
            r["bar"],
            improver=improver,
            rationale=r.get("rationale"),
            provenance={
                "challenge_id": r.get("challenge_id"),
                "frontier_revision": r.get("frontier_revision"),
                "model": r.get("model"),
                "attempts": r.get("proposals") or r.get("attempts") or [],
                "budget": budget.receipt(),
                "quality_diversity": diversity_decision,
            },
            fitness_version=fitness_version,
            retain_parent=bool(diversity_decision and diversity_decision["retain_parent"]),
        )
        entry["status"] = status
        log.append(entry)
        if not changed:
            break
        accepted += 1
    budget.authorize_side_effect("warehouse_write")
    changed = save_state(state)
    return {
        "rounds": rounds,
        "accepted": accepted,
        "log": log,
        "artifacts": len(state.moments),
        "active": len(state.active_moments),
        "floor": min((strength(moment, fitness_version) for moment in state.active_moments), default=None),
        "changed": changed,
        "budget": budget.receipt(),
        "selection_policy": selection_policy,
    }


def run_triple_jump(path=WAREHOUSE, evolution_path=None, policy_path=None):
    budget = new_budget(policy_path) if policy_path else new_budget()
    budget.authorize_rounds(3)
    state = load_state(path, evolution_path=evolution_path)
    result = triple_jump(state.active_moments or [mint(seed=1), mint(seed=2)], improve)
    for transition in result["rounds"]:
        changed, status = accept_jump(
            state,
            transition["target"],
            transition["improved"],
            transition["bar"],
            improver="deterministic-triple-jump",
            provenance={"budget": budget.receipt()},
        )
        if not changed:
            raise ValueError(f"triple jump persistence failed: {status}")
    budget.authorize_side_effect("warehouse_write")
    save_state(state)
    result["budget"] = budget.receipt()
    return result


def main():
    ap = argparse.ArgumentParser(description="double-jump harness loop")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--triple-jump", action="store_true")
    ap.add_argument("--path", default=WAREHOUSE)
    ap.add_argument("--evolution-path")
    ap.add_argument("--improver", choices=["deterministic", "brainstem", "copilot-cli"], default="deterministic")
    ap.add_argument("--brainstem-url", default="http://127.0.0.1:7071")
    ap.add_argument("--brainstem-timeout", type=float, default=90)
    ap.add_argument("--copilot-model", default="gpt-5.6-sol")
    ap.add_argument("--copilot-effort", choices=["low", "medium", "high", "xhigh", "max"], default="max")
    ap.add_argument("--fitness-version", choices=["v1", "v2"], default="v1")
    ap.add_argument("--policy")
    ap.add_argument("--selection-policy", choices=["floor", "quality-diversity"], default="floor")
    a = ap.parse_args()
    if a.triple_jump:
        res = run_triple_jump(a.path, a.evolution_path, a.policy)
        print(json.dumps({"triple_jump": res["rounds"], "champion": res["champion"]["t"],
                          "strength": res["strength"]}, indent=2, default=lambda value: value.get("t")))
    else:
        fitness_version = FITNESS_V1 if a.fitness_version == "v1" else FITNESS_V2
        try:
            result = run(a.rounds, a.path, a.evolution_path, a.improver,
                         a.brainstem_url, a.brainstem_timeout,
                         a.copilot_model, a.copilot_effort, fitness_version, a.policy,
                         a.selection_policy)
        except PolicyViolation as exc:
            print(json.dumps(exc.as_dict(), indent=2))
            raise SystemExit(1)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
