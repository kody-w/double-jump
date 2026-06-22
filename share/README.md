# DoubleJump — improve *anything*, autonomously

A single-file agent that turns any RAPP brainstem into a relentless improvement machine. It's the
[double-jump](../HARNESS.md) harness, stripped of any domain: point it at **anything you can score** and it
keeps raising the floor until you say stop.

> **The split that makes it universal:** the **agent** is the *harness* (it holds the candidates + scores,
> always points you at the weakest, checks each improvement actually leapfrogs the bar, counts generations,
> keeps the audit trail). The **model** is the *domain intelligence* (it decides how to score a thing and
> how to improve it). You bring the judgment; it brings the discipline.

## Install (for your workers)

Drop **`double_jump_agent.py`** into your brainstem's agents directory (or `AGENTS_PATH`). That's it —
no dependencies, no config. Then drive it from `/chat`.

```bash
cp double_jump_agent.py /path/to/your/brainstem/agents/
```

## Use it

Just tell your brainstem what to improve. The model drives the loop for you:

> *"Use DoubleJump to improve our onboarding email. Score 0-100 on clarity + warmth + conversion.
> Run 10 rounds, then show me the best."*

Under the hood the model loops these actions (you never have to):

| action | what it does |
|---|---|
| `start` | begin a project: a **goal** + the **rubric** you'll score by (and an optional `margin`) |
| `add` | record a candidate with your **0-100** score |
| `weakest` | get the next target + **the bar to beat** (a real leapfrog, not a nudge) |
| `improve` | submit a stronger version of the weakest + its score; it **retires** the weakest so the floor rises |
| `status` | ranked leaderboard + generation + **floor / ceiling / average** |
| `score` | re-judge an item · `list` projects · `reset` a project |

Every improvement must clear `max(weakest + margin, next-rung-up)` to count as a **double jump**. A version
that scores lower than its target is recorded but **can't lower the floor**. State persists to
`~/.double_jump/<project>.json`, so progress survives restarts, and multiple `project`s run in parallel.

## What you can point it at

Anything with a notion of "better": **code** (score on correctness/perf/readability), **copy**
(clarity/persuasion), a **UI** (usability), a **prompt** (output quality), a **plan** (risk/ROI), a
**dataset** (cleanliness), a **design**, a **pitch**, a **résumé**… If you can score it 0-100, DoubleJump
will relentlessly leapfrog the weakest until it stops getting better.

## The rule, in one line

> **Find the weakest. Leapfrog it by a margin. Retire it. Repeat — until the floor stops rising.**

Single-file, dependency-free, MIT-spirited to share. Part of [double-jump](https://github.com/kody-w/double-jump).
