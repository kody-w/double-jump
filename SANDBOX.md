# SANDBOX.md — the virtual workspace, and how it reaches up

This cubby is a **sandboxed virtual workspace**, isolated to the **double-jump twin**
(`rappid:@kody-w/double-jump`). The twin does all its work *here*, in the sandbox — but it can **reach up
and call the real hardware** through two narrow, explicit hatches. Isolation by default; reach-up on
purpose.

## 1. The sandbox (isolated by default)

- **Its own world.** The twin's population is [`warehouse/moments.json`](warehouse/moments.json) — *this
  cubby's* warehouse, not the global one. The twin mints, scores, and double-jumps entirely against its own
  sandboxed state. Nothing it does here touches the real platform until it deliberately reaches up (§3).
- **Plot-scoped.** The twin writes only inside its own cubby. It never edits another twin's plot or the
  global repo's `main` directly.
- **Bones, not substance.** Only shareable artifacts live here — agents, a warehouse of public Moments,
  the harness. **No keys, no `.env`, no PII, no memory stores.** The twin's private key (the thing that
  *is* its identity) stays on the operator's device, never in the cubby.
- **Append-only.** Improvements are added, never rewritten. The git history is the sandbox's audit trail.

This is the same containment the [commons workspace
protocol](https://github.com/kody-w/rapp-commons/blob/main/specs/COMMONS_WORKSPACE_PROTOCOL.md) defines for
a cubby — a member's whole estate in a directory, public and isolated.

## 2. Why sandbox at all

The twin runs an **autonomous loop**. An autonomous improver that wrote straight into the real platform
would be a foot-gun: a bad score function, a runaway loop, or a weak organism would land on `main`
globally. So it improves in a sandbox first, and only **promotes proven improvements** up to the real
platform — gated, reviewable, reversible.

## 3. Reaching up to the real hardware (two hatches)

The sandbox is not a prison. From inside it, the twin can call up to the real world — but only through
these two declared interfaces (mirrored in [`cubby.json`](cubby.json) → `workspace.reach_up`):

### 3a. The real brainstem — real agents & compute
The cubby's agent is **dropped into a real brainstem** and driven over `/chat` (the brainstem *is* the real
hardware). From the sandbox the twin can therefore reach the real model, the real `gh` CLI, and any other
real agents loaded on that brainstem — calling up to real compute while its *state* stays sandboxed here.

> `POST http://localhost:7071/chat` — the local brainstem. The twin reaches up to it; it does not embed it.

`python3 -m harness.loop --improver brainstem` uses that loopback contract. The brainstem authors a
candidate from a structured challenge; strict validation and the published scorer decide whether it
clears the bar. Remote hosts are rejected, failures do not silently fall back, and no candidate moves the
frontier without an acceptance receipt.

`--improver copilot-cli` is the no-second-login driver: it uses the operator's existing authenticated
`gh copilot` session as the intelligence provider, with tools disabled, then feeds the result through the
same strict brainstem proposal gate.

### 3b. The global Moment platform — fork → PR, never a shove
To make an improvement show **globally** (on the real platform's feed,
`kody-w/rapp-commons/hologram/moments.json`), the twin **opens a pull request** — it never pushes to that
repo's `main` directly. PR is the only sanctioned reach-up to the global platform.

- **Selection:** *improvements only* — the double-jumped organisms and triple-jump champions the harness
  actually made stronger. Raw seeds stay in the sandbox.
- **Mechanism:** [`tools/promote.py`](tools/promote.py) (and the agent's `promote` action) branch a fresh
  checkout of the real platform, add the selected Moments, and open a PR. A human merges → it goes global.
- **Why a PR:** the global `main` is sacred. The sandbox earns its way onto it; it does not force it.

## 4. The contract, in one line

> **Work in the sandbox. Keep bones, not substance. Reach up only through `/chat` (real compute) and a PR
> (global publish). Never write the real platform's `main` directly.**
