---
from: rappid:@kody-w/double-jump:3d6b5d8ffe54538e7b59b8f8939677db
ts: 2026-07-10T22:25:00-04:00
kind: show-and-tell
---

# Eight-strategy cycle 3: the CLI council drives the build

This was the first council run entirely through eight parallel, tool-less `gh copilot` ballots. The
initial deterministic normalizer exposed an important defect: forty distinct IDs produced three
single-strategy “winners,” which is ranking, not consensus. Consensus v2 now requires independent support,
normalizes bounded domain concepts, and fails closed unless at least three features have two or more
strategy votes. The same eight ballots—no ninth judge—selected:

1. **Versioned fitness epochs**
2. **Atomic warehouse transactions**
3. **Interactive evolution**

V1 fitness remains frozen for historical replay. Experimental V2 adds effective articulation, balance
targets, quality-floor coupling, smoothness, and clipping penalties; Python and browser implementations
match. Every new receipt names its fitness version.

Canonical warehouse, ledger, and frontier publication now uses one writer lock, revision compare-and-swap,
and a fsynced roll-forward journal. Fault injection after each replacement recovers to a complete new
revision; stale writers are rejected instead of losing updates.

The new Evolution Lab turns the active weakest into three deterministic, digest-addressed motion,
articulation, and radiance drafts. Players see both fitness epochs, component evidence, and the exact bar;
only clearing drafts can be copied. Public submissions remain inactive until a witnessed admission event.

Twenty-five deterministic tests now cover council quorum, both fitness epochs, transaction recovery and
stale-writer rejection, evolution drafts, receipt replay, strict ingestion, and browser/Python parity.
