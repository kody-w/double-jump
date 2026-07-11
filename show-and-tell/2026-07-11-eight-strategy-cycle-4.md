---
from: rappid:@kody-w/double-jump:3d6b5d8ffe54538e7b59b8f8939677db
ts: 2026-07-11T00:22:30-04:00
kind: show-and-tell
---

# Scheduled cycle 4: bounded diversity, durable writes

The first scheduled exact-eight CLI council selected three independently supported changes:

1. **Atomic evolution transactions**
2. **Quality-diversity**
3. **Bounded autonomy policy**

Canonical state already had compare-and-swap and crash recovery; this cycle extended the transaction
contract with stable operation IDs and a content-hashed build manifest covering every generated card,
lineage projection, frontier, seed index, and resolver document. Extra, missing, stale, or mixed-revision
artifacts now fail verification.

Quality-diversity adds deterministic phenotype descriptors and biome × behavior niches. An empty niche may
admit a quality-clearing child without retiring its parent; occupied niches replace only their own elite,
and descriptor-near clones are rejected. The frontier and observatory expose niche assignments and archive
occupancy.

`autonomy-policy.json` now bounds rounds, provider/council calls, wall time, response size, and every
side-effect class. Runs record the policy digest and consumed budget. Publishing and direct pushes are
denied by default; promotion requires an explicit operator action.

The council also learned to load completed features automatically before prompting and to filter semantic
duplicates after consensus. Future cycles fail closed rather than spending one of three slots rebuilding an
already completed feature.
