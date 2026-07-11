# The Double-Jump Harness — a pattern for autonomously improving things

**Double Jump** is a small, domain-agnostic pattern for making a population of things get better over
time, by itself, with git as the control surface. It is the engine inside this repo; Moments are just the
first thing it improves.

## The loop

```
            ┌──────────────────────────────────────────────────────────┐
            │                                                          │
   candidates() ──▶ strength(x) ──▶ pick the WEAKEST ──▶ improve() ──┐ │
            ▲                                                        │ │
            │                                          clear the weakest
            │                                          by a MARGIN? ──┤ │
            │                                                yes      │ │
            └────────────── submit() ◀── append-only commit ◀────────┘ │
                                                                        │
                                          (repeat — the frontier rises) │
            ────────────────────────────────────────────────────────────
```

1. **`candidates()`** — read the current population (here: a static `warehouse/moments.json`, served from a
   CDN like everything in the ecosystem).
2. **`strength(x)`** — a fitness scalar. The harness improves whatever scores lowest, so the only thing a
   new domain must supply is "what does *better* mean here?"
3. **Pick the weakest** — the lowest-strength candidate is the target. Improving the floor raises the whole
   population's floor.
4. **`improve(x)` until it clears the weakest by a `MARGIN`** — this is the **double jump**: don't just edge
   past the weakest, *leapfrog* it (clear `max(weakest + margin, second-weakest)`). If one nudge isn't
   enough, escalate the boost and try again.
5. **`submit()`** — append the immutable child plus a parent→child acceptance receipt. The parent retires
   from the active frontier but remains in history.
6. **Repeat.**

## Git is the harness

Every accepted improvement is an **append-only lineage event**. `warehouse/moments.json` stores unique
immutable artifacts; `warehouse/evolution.json` stores acceptance/tombstone events; and
`warehouse/frontier.json` is the generated active view. So:

- the repo's **history *is* the record** of the population improving — `git log` is the training curve;
- nothing is ever rewritten (the birth-proof / provenance of every prior thing stays intact);
- two harnesses (a CI cron, a human, an agent) can all push improvements; the **push-race** (fast-forward
  wins) is the consensus, exactly as in the Moment chain.

This is the same git-as-harness discipline the [Moment standard](https://github.com/kody-w/rapp-moment)
uses for organism growth — generalized to "improve *anything* you can score."

## The `Domain` interface

A domain plugs four things into [`harness/loop.py`](harness/loop.py):

| Hook | Meaning |
|---|---|
| `candidates()` | the population to improve |
| `strength(x)` | the fitness scalar (higher = better) |
| `improve(x, boost)` | produce a stronger variant (boost escalates the effort) |
| `submit(x)` | persist the improvement (append-only) |

Fitness is versioned per receipt. V1 remains replayable forever; V2 is an opt-in balance-seeking epoch.
The active challenge, bar, score breakdown, and acceptance event always name the exact fitness profile, so
calibration changes cannot silently rewrite history.

The Moment domain ([`harness/strength.py`](harness/strength.py) + [`harness/moment.py`](harness/moment.py))
defines strength as **vitality-gated motion/glow/spike energy + articulation** — the canonical
`rapp-hologram` metrics. Swap those two files and the same loop improves a different thing.

## Double jump vs. triple jump

- **Double jump** (the loop) — *continuous*: always leapfrog the current weakest by a margin. The frontier
  rises forever.
- **Triple jump** (the tournament, [`triple-jump/SPEC.md`](triple-jump/SPEC.md)) — *bracketed*: three
  elimination hops; the organism standing at the end "**won the triple jump**." This repo houses it.

Both are "jumps" (the track-and-field metaphor): the continuous improver and the tournament that crowns a
champion, over the same population, by the same `strength`.

## The eight-strategy product council

`python3 tools/run_council.py` runs exactly eight fixed strategy lenses against the same content-addressed
repository snapshot through the authenticated GitHub Copilot CLI. Calls are independent and tool-less.
Every strategy must return five strict proposals; any missing ballot aborts the cycle. Consensus is
deterministic (independent-strategy support, average priority, Borda score, stable tie-breaks), and the top
three plus all ballot hashes are stored as an append-only council receipt.

Canonical state publication is a journaled compare-and-swap transaction guarded by one writer lock.
Warehouse artifacts, evolution receipts, and the generated frontier roll forward together after a crash;
stale writers must reload and recompute instead of rebasing an already-scored decision.

Generated cards, lineage projections, and resolver documents are covered by
`warehouse/build-manifest.json`; exact file-set and content hashes expose stale or mixed revisions.

`autonomy-policy.json` is the single side-effect and budget contract. Rounds, model calls, wall time, and
promotion permissions are checked before use and written into receipts. Policy rejection never mutates
canonical state.

## Three ways to drive it

- **Agent** — drop [`agents/double_jump_agent.py`](agents/double_jump_agent.py) into a RAPP brainstem and
  drive it via `/chat`: `scan` → `weakest` → `jump` → `submit` → `loop`.
- **CLI** — `python3 -m harness.loop --rounds 3 --improver brainstem` asks the loopback RAPP brainstem to
  author candidates. Omit `--improver brainstem` for the seeded deterministic lab fallback.
- **CI** — [`.github/workflows/harness.yml`](.github/workflows/harness.yml) is manual-only because a hosted
  runner cannot reach the operator's local brainstem. [`ingest.yml`](.github/workflows/ingest.yml) accepts
  validated create/read issue operations.

*Engine, not experience. Append-only. Self-improving.*
