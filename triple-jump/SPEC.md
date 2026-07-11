# Triple Jump — the tournament (housed)

**Version 1.0 · status: living**

A **triple jump** is a three-hop elimination tournament over a population of living
[Moments](https://github.com/kody-w/rapp-moment). The organism standing at the end **"won the triple
jump"** — the phrase already stamped on the champions in the public warehouse. This document formalizes
and houses it.

## The rules

Given a pool of Moments and the `strength` function (vitality-gated motion/glow/spike energy +
articulation — see [`../harness/strength.py`](../harness/strength.py)):

1. **Hop 1.** Take the **weakest** organism in the pool and **double-jump** it — improve it until it
   clears the weakest by a margin (leapfrog, don't edge). The improved organism re-enters the pool in
   place of the one it bettered.
2. **Hop 2.** Repeat on the *new* weakest.
3. **Hop 3.** Repeat once more.

The organism produced by the third hop is the **champion**; its title is stamped `… · won the triple
jump`. Three consecutive margin-clearing improvements is a triple jump.

> **Why three.** One hop is a *double jump* (clear the weakest by a margin). Three chained hops is the
> *triple jump* — the bracketed, crown-a-champion variant of the same continuous improver. Same pool,
> same `strength`, same append-only discipline.

## Invariants

A conforming run **MUST**:

1. Score by the published `strength` (no bespoke metric mid-tournament).
2. Each hop **MUST clear the bar** `max(weakest + margin, second_weakest)` — a real leapfrog, witnessed.
3. Be **append-only** — champions are *added*; no prior organism is rewritten or deleted (the birth-proof
   and provenance of every entrant stay intact, per the Moment standard §4/§9).
4. Stamp the champion deterministically (`<base title> · won the triple jump`) so winners are self-labeling.

## Run it

```bash
# CLI — one tournament, champion appended to the warehouse
python3 -m harness.loop --triple-jump

# Agent — through any RAPP brainstem
#   action=triple_jump   → returns the champion + per-round deltas + a live hologram iframe
```

The champion is a standard Moment: it has a share token, plays at
`https://kody-w.github.io/rapp-hologram/?m=<token>`, and embeds as looping card art anywhere. It can be
submitted back to the network through the normal [issue-ops CRUD](../.github/ISSUE_TEMPLATE/submit.yml).

## Provenance

The warehouse was seeded from the original public "triple jump" winners in the RAPP Commons hologram
warehouse — the `Stillness`/`Frenzy`/`Ascent` organisms that first carried the title. The double-jump
harness now keeps raising their floor.
