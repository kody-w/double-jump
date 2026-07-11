# Double Jump

> 🧬 **This repo is the [double-jump twin's](front_door.md) cubby — a sandboxed virtual workspace**
> (`rappid:@kody-w/double-jump`). The twin improves in isolation here and **reaches up** to real hardware
> only through two hatches: the local brainstem (real compute) and a PR to the global platform. See
> **[SANDBOX.md](SANDBOX.md)**.

**An autonomous improvement harness.** Things compete; the **weakest** gets **double-jumped** — replaced
by a stronger one that leapfrogs it by a margin. Git is the harness, so the repo's history *is* the record
of the population getting better. The first thing it improves is a warehouse of living
[**RAPP Moments**](https://github.com/kody-w/rapp-moment) (100-frame holographic organisms), and it
**houses the [triple jump](triple-jump/SPEC.md)** tournament that crowns champions.

> Built on two standards it "plays ball" with: the **[rapp-moment](https://github.com/kody-w/rapp-moment)**
> wire format and the **[rapp-hologram](https://github.com/kody-w/rapp-hologram)** engine (the live player
> behind every card's iframe). The pattern itself is in **[HARNESS.md](HARNESS.md)**.

## What's here

| Path | What |
|---|---|
| [`agents/double_jump_agent.py`](agents/double_jump_agent.py) | a **brainstem-drivable** agent: `scan · weakest · jump · triple_jump · submit · loop` |
| [`harness/`](harness/) | the loop engine — strict validation, fitness, active-lineage storage, local-brainstem proposals, and the deterministic referee |
| [`triple-jump/SPEC.md`](triple-jump/SPEC.md) | the housed three-hop tournament |
| [`warehouse/moments.json`](warehouse/moments.json) | the static population the harness improves |
| [`arena.html`](arena.html) | the **3D arena** — every organism in one world, animated by its genome, ranked by strength; click **Evolve** to double-jump the weakest (the evolution sim) |
| [`evolve.html`](evolve.html) | the **Evolution Lab** — three deterministic, digest-addressed motion/articulation/radiance drafts for the active weakest |
| [`evolution.html`](evolution.html) | the **Evolution Observatory** — replay-verifiable lineage receipts beside exact-eight product council decisions |
| [`pokedex.html`](pokedex.html) + [`cards.json`](cards.json) | the **Holodex** — each creature as a `rappcards/1.0` holocard whose art is the live hologram; federated via [`peers.json`](peers.json) |
| [`index.html`](index.html) | the gallery — every card's art is a **live hologram iframe** looping 100 frames |
| [`tools/ingest.py`](tools/ingest.py) + [`tools/promote.py`](tools/promote.py) + [`.github/`](.github/) | the static-API **issue-ops CRUD**, the reach-up **promote**, + the scheduled loop |
| [`share/double_jump_agent.py`](share/double_jump_agent.py) | the **generic** double-jump harness — a standalone agent to autonomously improve *anything you can score* (code, copy, prompts, plans…). [How to use](share/README.md) |

## Quickstart

```bash
# rank the warehouse weakest -> strongest
python3 - <<'PY'
from harness.loop import load_warehouse
from harness.strength import rank
for m in rank(load_warehouse())[:5]:
    print(round(m['_strength'],4), m['t'])
PY

# double-jump the weakest (appends a stronger organism, append-only)
python3 -m harness.loop --rounds 1

# ask the local RAPP brainstem to author candidates; the harness still validates + scores
python3 -m harness.loop --rounds 1 --improver brainstem

# reuse the already-authenticated GitHub Copilot CLI as the brainstem's intelligence
python3 -m harness.loop --rounds 1 --improver copilot-cli

# opt into the experimental balance-seeking fitness epoch
python3 -m harness.loop --rounds 1 --improver copilot-cli --fitness-version v2

# preserve distinct biome × behavior elites instead of optimizing one monoculture
python3 -m harness.loop --rounds 1 --improver copilot-cli --selection-policy quality-diversity

# run one exact-eight product council over an immutable repository snapshot
python3 tools/run_council.py

# crown a triple-jump champion
python3 -m harness.loop --triple-jump
```

### Drive it through a brainstem

```bash
# point a RAPP brainstem at this repo's agents, then /chat the DoubleJump agent
AGENTS_PATH=/path/to/double-jump/agents ./start.sh
# "scan the warehouse" · "double-jump the weakest" · "submit that as a gist" · "run the loop 3 times"
```

`challenge` gives the local brainstem the active target and objective bar; `propose` validates and scores
the child it authored. The model supplies creative intelligence, while the deterministic harness remains
the referee. `jump` is the explicit seeded offline fallback. Accepted jumps append a receipt to
`warehouse/evolution.json`; the parent leaves the active frontier but remains immutable history.

If the brainstem's own Copilot token is unavailable, `--improver copilot-cli` invokes the locally
installed, already-authenticated `gh copilot` command in noninteractive/no-tools mode. It uses the same
challenge/proposal/referee contract and requires no second device-code login.

Proposal prompts contain numeric genome evidence—not submitted titles/authors—and request keyframes only.
The provider must echo a revision-bound challenge ID in one strict JSON object. Tools and built-in MCPs are
disabled; the harness restores identity, validates, scores, and records a hash-chained receipt.

`submit` can publish a Moment as a **public gist** and open a create-only **moment-submit issue**, but the
default autonomy policy denies publishing. An operator must deliberately change that policy first. Public
update/delete remain unavailable until signed lineage operations exist.

## How a Moment is scored

`strength ∈ [0,1]` = **vitality-gated** ( `1 - stress/12`, from the engine's homeostasis ) × a blend of
**articulation** (keyframes), **motion** (x/z path), **jerk**, **glow**, **spike**, and **variance** energy
— the canonical `rapp-hologram` fingerprint terms. So a flat 2-keyframe "Stillness" is weak; a dynamic,
many-keyframe "Frenzy" is strong, and the harness keeps raising the floor between them.

Historical receipts remain pinned to `double-jump-strength/1.0`. The optional
`double-jump-strength/2.0` profile resists keyframe stuffing and saturated extrema through effective
articulation, target ranges, quality-floor coupling, smoothness, and clipping penalties. Both Python and
browser implementations are parity-tested; changing epochs never rewrites old scores.

The optional quality-diversity policy derives deterministic phenotype descriptors and biome × behavior
niches. An empty niche can admit a quality-clearing child without retiring its parent; occupied niches
replace only their own elite and descriptor-near clones are rejected.

Every autonomous entry point is bounded by [`autonomy-policy.json`](autonomy-policy.json): rounds,
provider/council calls, runtime, response size, and side effects fail closed. Accepted receipts record the
policy digest and consumed budget.

The active frontier is materialized in `warehouse/frontier.json`. Historical observations are
content-addressed and deduplicated, so an identical scheduled result is a no-op rather than another
competitor.

## Card art is a live hologram

Every entry is portable card art. The token is `base64url(JSON)`; the iframe streams it from a CDN and
loops all 100 frames:

```html
<iframe src="https://kody-w.github.io/rapp-hologram/?m=<TOKEN>" width="320" height="320" loading="lazy"></iframe>
```

This is the Moment standard's Gateway `animation_url` (§11¾) — the *actual walkable hologram* renders
in-place.

## License

Source-available under **PolyForm Noncommercial 1.0.0** ([`LICENSE`](LICENSE) / [`NOTICE`](NOTICE)).
"RAPP", "Holographic Moments" are trademarks of Kody Wildfeuer; the license grants no trademark rights.

*Engine, not experience. Append-only. Self-improving.*
