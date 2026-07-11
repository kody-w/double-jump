"""
DoubleJump — a generic, autonomous improvement harness you can point at ANYTHING.

Drop this single file into any RAPP brainstem's agents directory and drive it through /chat. It is
domain-agnostic: it does not know or care whether you are improving code, marketing copy, a UI, a prompt,
a business plan, a poem, or a dataset. It only enforces one ruthless discipline — the **double jump**:

    find the WEAKEST thing  ->  improve it until it LEAPFROGS the next one up (clears it by a margin)
    ->  record it (append-only)  ->  repeat, forever, until you say stop.

The split that makes it universal:
  - THE AGENT is the harness — it holds the population + scores, always points you at the weakest, checks
    that each improvement actually clears the bar, counts generations, and keeps the full audit trail.
  - THE LLM (you, the caller) is the domain intelligence — you decide HOW to score a thing (any 0-100
    fitness you want) and HOW to improve it. The agent makes you honest about always raising the floor.

Typical autonomous loop the caller runs:
    start  (goal + how you'll score)  ->  add a few candidates  ->  weakest  ->  improve  ->  weakest
    ->  improve  ->  ...  (the floor keeps rising)  ->  status  any time.

State persists to ~/.double_jump/<project>.json, so the population survives across calls and restarts.
Multiple independent projects are supported via the `project` arg.

Single-file, dependency-free, brainstem-drivable. Share it with anyone. Compatible with the RAR registry
at https://github.com/kody-w/RAR.
"""
import json
import math
import os
import tempfile
import time

try:
    from basic_agent import BasicAgent
except Exception:
    class BasicAgent:
        def __init__(self, name=None, metadata=None):
            if name is not None:
                self.name = name
            if metadata is not None:
                self.metadata = metadata
        def perform(self, **k):
            return "Not implemented."

STATE_DIR = os.path.join(os.path.expanduser("~"), ".double_jump")
DEFAULT_MARGIN = 6.0          # on a 0-100 fitness scale, a "double jump" must clear the weakest by this much


def _path(project):
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (project or "default")) or "default"
    return os.path.join(STATE_DIR, safe + ".json")


def _load(project):
    try:
        return json.load(open(_path(project)))
    except Exception:
        return {"schema": "double-jump/1.0", "project": project, "goal": "", "margin": DEFAULT_MARGIN,
                "generation": 0, "items": [], "history": []}


def _save(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    path = _path(state["project"])
    fd, temporary = tempfile.mkstemp(prefix=".double-jump-", suffix=".tmp", dir=STATE_DIR, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(state, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _score(value):
    score = float(value)
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("score must be finite and in [0, 100]")
    return score


def _ranked(items):
    return sorted([it for it in items if it.get("active", True)], key=lambda it: it.get("score", 0))  # active, weakest first


def _clip(s, n=240):
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


class DoubleJumpAgent(BasicAgent):
    def __init__(self):
        self.name = "DoubleJump"
        self.metadata = {
            "name": self.name,
            "description": (
                "A generic autonomous-improvement harness — point it at ANYTHING you can score (code, copy, "
                "a UI, a prompt, a plan, a design, data) and it relentlessly raises the floor. It enforces "
                "the 'double jump' discipline: always improve the WEAKEST candidate, and make each "
                "improvement LEAPFROG the next one up by a margin; everything is append-only and "
                "generation-tracked. YOU (the model) supply the domain judgment: you assign each candidate a "
                "0-100 fitness score by whatever criteria fit the goal, and you write the improvements. The "
                "agent tells you what to improve next and whether you actually cleared the bar. Use it to "
                "autonomously, iteratively improve a piece of work over many rounds. Actions: 'start' (begin "
                "a project with a goal + scoring rubric), 'add' (record a candidate with a score), 'weakest' "
                "(get the next target + the bar to beat), 'improve' (submit a better version of the weakest), "
                "'status' (ranked leaderboard + generation + floor), 'score' (re-judge an item), 'list' "
                "(projects), 'reset' (clear a project). Drive it in a loop: weakest -> improve -> weakest -> "
                "improve, until the user says stop."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string",
                               "enum": ["start", "add", "weakest", "improve", "status", "score", "list", "reset"],
                               "description": "What to do. Default 'status'."},
                    "project": {"type": "string", "description": "Project name (lets you improve several things in parallel). Default 'default'."},
                    "goal": {"type": "string", "description": "For 'start': what you are improving and the rubric you will score by (e.g. 'landing page copy; score 0-100 on clarity+persuasion')."},
                    "content": {"type": "string", "description": "For 'add'/'improve': the candidate/version itself (code, text, a plan — anything)."},
                    "score": {"type": "number", "description": "For 'add'/'improve'/'score': YOUR 0-100 fitness judgment of this candidate by the project's rubric. Be honest and consistent."},
                    "label": {"type": "string", "description": "Optional short name for this candidate/version."},
                    "id": {"type": "string", "description": "For 'score': the item id to re-judge."},
                    "margin": {"type": "number", "description": "For 'start': how much an improvement must beat the weakest to count as a double jump (0-100 scale, default 6)."},
                },
                "required": [],
                "additionalProperties": True,
            },
        }
        super().__init__(name=self.name, metadata=self.metadata)

    def _env(self, action, **kw):
        return json.dumps(dict(schema="double-jump-result/1.0", agent="DoubleJump", action=action, **kw),
                          indent=2, ensure_ascii=False)

    def _snapshot(self, state):
        active = [it for it in state["items"] if it.get("active", True)]
        scores = [it.get("score", 0) for it in active]
        return {
            "project": state["project"], "goal": state["goal"], "generation": state["generation"],
            "population": len(active), "retired": len(state["items"]) - len(active), "margin": state["margin"],
            "floor": round(min(scores), 2) if scores else None,
            "ceiling": round(max(scores), 2) if scores else None,
            "average": round(sum(scores) / len(scores), 2) if scores else None,
            "leaderboard": [{"rank": i + 1, "id": it["id"], "score": it.get("score", 0),
                             "label": it.get("label") or it.get("id"), "gen": it.get("gen", 0)}
                            for i, it in enumerate(sorted(active, key=lambda x: -x.get("score", 0)))][:12],
        }

    def _weakest(self, state):
        r = _ranked(state["items"])
        if not r:
            return None
        weak = r[0]
        bar = weak.get("score", 0) + state["margin"]
        if len(r) > 1:                                   # a true double jump also reaches the next rung up
            bar = max(bar, r[1].get("score", 0))
        return weak, round(bar, 2)

    def _record(self, state, content, score, label, gen=0, improved_from=None, active=True):
        item = {"id": f"v{len(state['items']) + 1}", "content": (content or "").strip(),
                "score": _score(score) if score is not None else 0.0,
                "label": (label or "").strip() or _clip(content, 40), "gen": gen, "active": active,
                "improved_from": improved_from, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        state["items"].append(item)
        return item

    def perform(self, **kwargs):
        action = (kwargs.get("action") or "status").strip().lower()
        project = (kwargs.get("project") or "default").strip()
        state = _load(project)
        state["project"] = project

        if action == "start":
            state["goal"] = (kwargs.get("goal") or state.get("goal") or "").strip()
            if kwargs.get("margin") is not None:
                try:
                    state["margin"] = _score(kwargs["margin"])
                except (TypeError, ValueError) as exc:
                    return self._env("start", status="error", error=str(exc))
            if kwargs.get("content"):
                try:
                    self._record(state, kwargs.get("content"), kwargs.get("score"), kwargs.get("label"), gen=0)
                except (TypeError, ValueError) as exc:
                    return self._env("start", status="error", error=str(exc))
            _save(state)
            return self._env("start", status="ready", project=project, goal=state["goal"], margin=state["margin"],
                             how_to_drive=("Now: 'add' 2-4 starting candidates (each with your 0-100 score), then "
                                           "loop 'weakest' -> 'improve' -> 'weakest' -> 'improve'. I always point "
                                           "you at the lowest, and an improvement must clear it by the margin to "
                                           "count. Keep going until the floor stops rising or the user says stop."),
                             state=self._snapshot(state))

        if action == "add":
            if not kwargs.get("content"):
                return self._env("add", status="error", error="add needs content=<the candidate>.")
            try:
                it = self._record(state, kwargs["content"], kwargs.get("score"), kwargs.get("label"), gen=state["generation"])
            except (TypeError, ValueError) as exc:
                return self._env("add", status="error", error=str(exc))
            _save(state)
            nxt = self._weakest(state)
            return self._env("add", status="added", item=it["id"], score=it["score"],
                             weakest=(None if not nxt else {"id": nxt[0]["id"], "label": nxt[0].get("label"),
                                      "score": nxt[0]["score"], "beat_to_double_jump": nxt[1]}),
                             next="When you have a few candidates, call action=weakest to get the next target.",
                             state=self._snapshot(state))

        if action == "weakest":
            nxt = self._weakest(state)
            if not nxt:
                return self._env("weakest", status="empty", note="No candidates yet — 'add' some first.")
            weak, bar = nxt
            return self._env("weakest", status="target", target={
                "id": weak["id"], "label": weak.get("label") or weak["id"], "score": weak["score"],
                "content": weak.get("content", "")},
                beat_to_double_jump=bar,
                instruction=(f"Improve THIS candidate so a better version scores at least {bar} "
                             f"(currently {weak['score']}). Then call action=improve with content=<the better "
                             f"version> and score=<your honest 0-100 judgment>. Leapfrog it — don't just nudge."),
                state=self._snapshot(state))

        if action == "improve":
            if not kwargs.get("content") or kwargs.get("score") is None:
                return self._env("improve", status="error",
                                 error="improve needs content=<better version> and score=<your 0-100 judgment>.")
            nxt = self._weakest(state)
            if not nxt:
                return self._env("improve", status="error", error="nothing to improve yet — 'add' a candidate first.")
            target, bar = nxt
            target_score = target.get("score", 0)
            try:
                new_score = _score(kwargs["score"])
            except (TypeError, ValueError) as exc:
                return self._env("improve", status="error", error=str(exc))
            cleared = new_score >= bar
            state["generation"] += 1
            it = self._record(state, kwargs["content"], new_score, kwargs.get("label"),
                              gen=state["generation"], improved_from=target["id"], active=cleared)
            if cleared:
                target["active"] = False
            state["history"].append({"gen": state["generation"], "improved_from": target["id"],
                                     "new": it["id"], "score": new_score, "bar": bar,
                                     "beats_target": new_score >= target_score, "cleared": cleared, "ts": it["ts"]})
            _save(state)
            snap = self._snapshot(state)
            after = self._weakest(state)
            if new_score < target_score:
                msg = (f"That scored {new_score}, below the target's {target_score}. Kept the original; "
                       f"the floor did not drop. Try again with a genuinely stronger version.")
                status = "short"
            elif cleared:
                msg = f"DOUBLE JUMP — {new_score} >= {bar}. Retired the weakest; the floor is now {snap['floor']}."
                status = "double_jump"
            else:
                msg = (f"Better than the target, but {new_score} is short of the leapfrog bar {bar}. "
                       f"The original stays active and the floor remains {snap['floor']}.")
                status = "short"
            return self._env("improve", status=status, cleared=cleared, generation=state["generation"],
                             new_item=it["id"], message=msg,
                             next_weakest=(None if not after else {"id": after[0]["id"], "score": after[0]["score"],
                                            "beat_to_double_jump": after[1]}),
                             keep_going="Call action=weakest for the next target and improve again. The loop ends only when the floor stops rising or the user says stop.",
                             state=snap)

        if action == "score":
            it = next((x for x in state["items"] if x["id"] == kwargs.get("id")), None)
            if not it or kwargs.get("score") is None:
                return self._env("score", status="error", error="score needs id=<item> and score=<0-100>.")
            try:
                it["score"] = _score(kwargs["score"])
            except (TypeError, ValueError) as exc:
                return self._env("score", status="error", error=str(exc))
            _save(state)
            return self._env("score", status="rescored", item=it["id"], score=it["score"], state=self._snapshot(state))

        if action == "list":
            os.makedirs(STATE_DIR, exist_ok=True)
            projs = [f[:-5] for f in os.listdir(STATE_DIR) if f.endswith(".json")]
            return self._env("list", status="ok", projects=projs)

        if action == "reset":
            try:
                os.remove(_path(project))
            except Exception:
                pass
            return self._env("reset", status="cleared", project=project)

        if not state["items"]:
            return self._env("status", status="empty",
                             note=("Nothing here yet. Call action=start with goal=<what to improve + how you'll "
                                   "score 0-100>, then add candidates and loop weakest->improve."),
                             state=self._snapshot(state))
        return self._env("status", status="ok", state=self._snapshot(state),
                         next="Lowest score holds the floor. action=weakest to target it, action=improve to leapfrog it.")
