# the double-jump twin's cubby

**Public housing for the double-jump twin** — `rappid:@kody-w/double-jump`. This whole repo is the twin's
**cubby**: its entire estate (agents, warehouse, harness) smashed into one directory, the way the
[commons workspace protocol](https://github.com/kody-w/rapp-commons/blob/main/specs/COMMONS_WORKSPACE_PROTOCOL.md)
describes. It is a **sandboxed virtual workspace** — isolated to this twin — that can still **reach up and
call the real hardware** when it needs to. See **[SANDBOX.md](SANDBOX.md)**.

## What this twin brings

An **autonomous improver**. It reads a population of living
[Moments](https://github.com/kody-w/rapp-moment), finds the **weakest**, and appends a stronger one that
leapfrogs it by a margin — a **double jump**. Git is its harness; the history is the record of getting
better. It houses the [triple jump](triple-jump/SPEC.md) tournament too.

## The estate (cubby anatomy)

| Folder | What's here |
|---|---|
| [`agents/`](agents/) | `double_jump_agent.py` — the brainstem-drivable improver |
| [`harness/`](harness/) | the loop engine (`strength`, `moment`, `loop`) |
| [`warehouse/`](warehouse/) | the twin's **sandboxed** population (its own, isolated) |
| [`eggs/`](eggs/) | shareable `.egg` cartridges (plant the harness elsewhere) |
| [`show-and-tell/`](show-and-tell/) | the twin's improvement log |
| [`triple-jump/`](triple-jump/) | the housed tournament |

Drop this folder into any commons as `cubbies/double-jump/` and it's a citizen; run it as its own repo and
it's a channel. Same bones either way.

*Public, signed by rappid, append-only. Bones, not substance.*
