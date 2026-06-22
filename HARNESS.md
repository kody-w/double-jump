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
5. **`submit()`** — append the improvement. Never rewrite; the population only grows.
6. **Repeat.**

## Git is the harness

Every accepted improvement is an **append-only commit**. So:

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

## Three ways to drive it

- **Agent** — drop [`agents/double_jump_agent.py`](agents/double_jump_agent.py) into a RAPP brainstem and
  drive it via `/chat`: `scan` → `weakest` → `jump` → `submit` → `loop`.
- **CLI** — `python3 harness/loop.py --rounds 3` (or `--triple-jump`) improves the warehouse locally.
- **CI** — [`.github/workflows/harness.yml`](.github/workflows/harness.yml) runs the loop on a schedule and
  commits each improvement; [`ingest.yml`](.github/workflows/ingest.yml) accepts outside submissions via
  issue-ops.

*Engine, not experience. Append-only. Self-improving.*
