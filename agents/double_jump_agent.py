"""
DoubleJump — a brainstem-drivable agent that runs the autonomous improvement harness.

Drop this file into any RAPP brainstem's agents directory (or point AGENTS_PATH at double-jump/agents)
and drive it through /chat. It reads a warehouse of RAPP Moments, scores each by `strength` (vitality +
motion/glow/spike energy + articulation — the canonical rapp-hologram metrics), finds the WEAKEST, and
produces a stronger one that leapfrogs it by a margin (a "double jump"). It can publish a Moment as a
public GitHub **gist** (the shareable, CDN-served holo) and open a **submission issue** (the static-API,
issue-ops CRUD write path) so a workflow commits it into the network.

Actions:
  scan                      rank the warehouse weakest -> strongest
  weakest                   the single weakest Moment (the next target) + its live player URL
  jump        [token=]      double-jump the weakest (or a given token): improve until it clears the bar
  triple_jump               run a 3-round elimination tournament -> a champion that "won the triple jump"
  submit      token= [...]  publish a Moment as a public gist + open a moment-submit issue (CRUD: create)
  loop        rounds= [submit=true]   autonomously: find weakest -> jump -> (optionally) submit, N times

Every result includes the canonical share token and a ready-to-embed iframe: the card art is the live
hologram (PLAYER_BASE/?m=<token>) looping its 100 frames. MVP Moments are unsigned (matching the public
warehouse). Single-file, dependency-free; uses the `gh` CLI for gist/issue when submitting.

Auto-generated for kody-w/double-jump. Compatible with the RAR registry at https://github.com/kody-w/RAR
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

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

PLAYER_BASE = "https://kody-w.github.io/rapp-hologram/"
TARGET_REPO = "kody-w/double-jump"
FRONTIER_RAW = "https://raw.githubusercontent.com/kody-w/double-jump/main/warehouse/frontier.json"

# Prefer the repo's canonical harness library (single source of truth); fall back to an embedded copy so
# this file still works dropped into any brainstem on its own.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    from harness.moment import mint, improve, encode_token, decode_token
    from harness.strength import strength, rank, weakest
    from harness.loop import double_jump, triple_jump, WAREHOUSE as _WH_PATH
    from harness.store import load_state as _load_state
    from harness.validation import moment_id
    from harness.policy import PolicyViolation, new_budget
    _SRC = "harness"
except Exception:                                                    # pragma: no cover - drop-in fallback
    import base64 as _b64, random as _rnd
    _SRC = "embedded"
    _WH_PATH = os.path.join(_ROOT, "warehouse", "moments.json")
    _LIN, _DRIFT = ["s", "l", "p", "g"], ["x", "z"]
    _load_state = None
    PolicyViolation = RuntimeError
    new_budget = None

    def moment_id(m):
        return encode_token(m)

    def encode_token(m):
        raw = json.dumps(m, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return _b64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def decode_token(t):
        return json.loads(_b64.urlsafe_b64decode(t + "=" * (-len(t) % 4)).decode("utf-8"))

    def _expand(m, N=100):
        s = sorted(m.get("k", []), key=lambda f: f["at"]) or [{"at": 0}, {"at": 99}]
        out = []
        for i in range(N):
            at = i / (N - 1) * 99
            if at <= s[0]["at"]:
                out.append(s[0]); continue
            if at >= s[-1]["at"]:
                out.append(s[-1]); continue
            for j in range(len(s) - 1):
                a, b = s[j], s[j + 1]
                if a["at"] <= at <= b["at"]:
                    t = (at - a["at"]) / ((b["at"] - a["at"]) or 1)
                    out.append({f: a.get(f, 0) + (b.get(f, 0) - a.get(f, 0)) * t for f in _LIN + _DRIFT}); break
        return out

    def strength(m):
        fr = _expand(m); n = len(fr)
        path = sum(((fr[i]["x"] - fr[i - 1]["x"]) ** 2 + (fr[i]["z"] - fr[i - 1]["z"]) ** 2) ** 0.5 for i in range(1, n))
        glow = sum(f["g"] for f in fr) / n
        spike = sum(f["p"] for f in fr) / n
        gen = len(m.get("k", []))
        return round(0.30 * min(gen / 8., 1) + 0.25 * min(path / 5., 1) + 0.15 * glow + 0.08 * spike + 0.22 * min((sum(((sum((f[k] for f in fr)) / n) for k in _LIN)) / 4), 1), 4)

    def rank(ms):
        out = [dict(m, _strength=strength(m)) for m in ms]; out.sort(key=lambda m: m["_strength"]); return out

    def weakest(ms):
        return rank(ms)[0] if ms else None

    def mint(seed=None, **k):
        r = _rnd.Random(seed)
        return {"v": 1, "t": k.get("title", f"Mint {r.randint(1000,9999)}"), "a": k.get("author", "@double-jump"),
                "b": k.get("biome", "savanna"), "k": [{"at": 0, "s": .3, "l": .3, "p": .1, "g": .2, "h": 40, "x": 0, "z": 0},
                {"at": 99, "s": .5, "l": .4, "p": .2, "g": .4, "h": 120, "x": .3, "z": -.2}]}

    def improve(m, boost=1, seed=None):
        k = sorted((dict(f) for f in m.get("k", [])), key=lambda f: f["at"])
        for f in k:
            f["g"] = min(f.get("g", 0) + 0.08 * boost, 1); f["p"] = min(f.get("p", 0) + 0.05 * boost, 1)
            f["x"] = max(-1, min(1, f.get("x", 0) + 0.15 * boost)); f["z"] = max(-1, min(1, f.get("z", 0) - 0.1 * boost))
        out = dict(m); out["k"] = k; out["t"] = m.get("t", "Moment").split(" · ")[0] + " · double-jumped"; return out

    def double_jump(cands, improve_fn, **kw):
        ranked = sorted(cands, key=strength); target = ranked[0]
        bar = max(strength(target) + 0.05, strength(ranked[1]) if len(ranked) > 1 else 0)
        best = None
        for b in range(1, 9):
            c = improve_fn(target, boost=b, seed=b)
            if best is None or strength(c) > strength(best):
                best = c
            if strength(c) >= bar:
                break
        return {"target": target, "improved": best, "from": strength(target), "to": strength(best), "bar": round(bar, 4), "cleared": strength(best) >= bar}

    def triple_jump(cands, improve_fn, **kw):
        pool = [dict(m) for m in cands]; hist = []; champ = None
        for rnd in range(1, 4):
            r = double_jump(pool, improve_fn); champ = dict(r["improved"])
            champ["t"] = r["target"].get("t", "Moment").split(" · ")[0] + " · won the triple jump"
            pool = [m for m in pool if m is not r["target"]] + [champ]; hist.append({"round": rnd, "from": r["from"], "to": r["to"]})
        return {"champion": champ, "rounds": hist, "strength": strength(champ)}


def _run(args, stdin=None, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=stdin)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


class DoubleJumpAgent(BasicAgent):
    def __init__(self):
        self.name = "DoubleJump"
        self.metadata = {
            "name": self.name,
            "description": (
                "Run the double-jump autonomous improvement harness over a warehouse of RAPP Moments "
                "(living 100-frame holograms). It scores every Moment by strength (vitality + motion/glow/"
                "spike energy + articulation), finds the WEAKEST, and produces a stronger one that leapfrogs "
                "it by a margin (a 'double jump'). It can publish a Moment as a public GitHub gist and open a "
                "submission issue so the network commits it. Every result carries the share token and a live "
                "hologram iframe (the animated card art). Actions: 'scan' (rank weakest->strongest), 'weakest' "
                "(the next target), 'challenge' (target + objective bar for the brainstem), 'propose' "
                "(deterministically validate and score a brainstem-authored child), 'jump' (deterministic "
                "offline fallback for the weakest or a given token), 'triple_jump' (a 3-round "
                "tournament -> a champion), 'submit' (gist + moment-submit issue, CRUD create), 'loop' "
                "(autonomously find-weakest->jump->submit N rounds), 'promote' (reach up from the sandbox "
                "and open a PR promoting proven improvements to the GLOBAL rapp-commons Moment feed). Use when "
                "the user wants to improve, compete with, rank, publish, or globally promote holographic Moments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string",
                               "enum": ["scan", "weakest", "challenge", "propose", "jump", "triple_jump", "submit", "loop", "promote", "resolve"],
                               "description": "What to do. Default 'scan'."},
                    "token": {"type": "string", "description": "A Moment share token (base64url). For 'jump' a specific Moment, for 'propose' the child, or for 'submit' the Moment to publish."},
                    "target_token": {"type": "string", "description": "For 'propose': the exact challenged parent token. The candidate goes in token."},
                    "rounds": {"type": "integer", "description": "For 'loop': how many improvement rounds (default 1)."},
                    "submit": {"type": "boolean", "description": "For 'loop': also publish each improvement as a gist + issue (default false)."},
                    "title": {"type": "string", "description": "Optional title override for a minted/improved Moment."},
                    "biome": {"type": "string", "enum": ["savanna", "canyon", "forest", "volcanic", "void"],
                              "description": "Optional biome for a minted Moment."},
                    "apply": {"type": "boolean", "description": "For 'promote': actually open the PR (default false = dry-run that just lists what would be promoted)."},
                    "id": {"type": "string", "description": "For 'resolve': the holocard id to resolve (e.g. @double-jump/frenzy-8-...). Default = the champion (strongest)."},
                },
                "required": [],
                "additionalProperties": True,
            },
        }
        super().__init__(name=self.name, metadata=self.metadata)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _moment(self, m):
        return {key: value for key, value in m.items() if not key.startswith("_")}

    def _play(self, m):
        return PLAYER_BASE + "?m=" + encode_token(self._moment(m))

    def _iframe(self, m):
        return ('<iframe src="' + self._play(m) + '" width="320" height="320" loading="lazy" '
                'style="border:0;border-radius:12px" title="' + str(m.get("t", "Moment")).replace('"', "'") + '"></iframe>')

    def _card(self, m, extra=None):
        m = self._moment(m)
        c = {"title": m.get("t"), "author": m.get("a"), "biome": m.get("b"),
             "keyframes": len(m.get("k", [])), "strength": strength(m),
             "token": encode_token(m), "play_url": self._play(m), "iframe": self._iframe(m)}
        if extra:
            c.update(extra)
        return c

    def _load(self, kwargs):
        # explicit token list? no — load the warehouse: local file first, then the published raw CDN.
        p = kwargs.get("_warehouse_path") or _WH_PATH
        if os.path.exists(p):
            try:
                if _load_state is not None:
                    state = _load_state(p)
                    return state.active_moments, state.frontier_path
                d = json.load(open(p))
                return d.get("moments", d if isinstance(d, list) else []), p
            except Exception:
                pass
        try:
            with urllib.request.urlopen(FRONTIER_RAW, timeout=10) as r:
                d = json.loads(r.read().decode("utf-8"))
                entries = d.get("entries") or []
                return [entry["moment"] for entry in entries], FRONTIER_RAW
        except Exception:
            return [], None

    def _env(self, action, status, **kw):
        return json.dumps(dict(schema="rapp-result/1.0", agent="DoubleJump", action=action,
                               status=status, source=_SRC, **kw), indent=2)

    def _gist(self, m):
        body = json.dumps(m, indent=2)
        with tempfile.TemporaryDirectory() as d:
            fn = os.path.join(d, "moment.egg.json")
            open(fn, "w").write(body + "\n")
            desc = f"rapp-moment · {m.get('t','Moment')} · strength {strength(m)} · play {self._play(m)}"
            rc, out, err = _run(["gh", "gist", "create", fn, "--public", "-d", desc])
        if rc != 0:
            return None, err or "gist failed"
        url = out.split()[-1] if out else ""
        gid = url.rstrip("/").split("/")[-1]
        raw = f"https://gist.githubusercontent.com/{{user}}/{gid}/raw/moment.egg.json"
        return {"gist_url": url, "gist_id": gid, "raw_url_template": raw}, None

    def _issue(self, m, gist):
        token = encode_token(m)
        body = (
            f"### op\ncreate\n\n### Moment\n**{m.get('t','Moment')}** by {m.get('a','@anon')} · "
            f"biome `{m.get('b','savanna')}` · {len(m.get('k',[]))} keyframes · strength **{strength(m)}**\n\n"
            f"### gist\n{gist.get('gist_url','(none)') if gist else '(none)'}\n\n"
            f"### token\n```\n{token}\n```\n\n"
            f"### play\n{self._play(m)}\n\n### card art\n{self._iframe(m)}\n\n"
            f"_Submitted by the DoubleJump harness. The ingest workflow verifies + commits this to the warehouse._\n"
        )
        rc, out, err = _run(["gh", "issue", "create", "--repo", TARGET_REPO,
                             "--title", f"moment-submit: {m.get('t','Moment')}",
                             "--body", body, "--label", "moment-submit"])
        if rc != 0:
            # retry without the label in case it doesn't exist yet
            rc, out, err = _run(["gh", "issue", "create", "--repo", TARGET_REPO,
                                 "--title", f"moment-submit: {m.get('t','Moment')}", "--body", body])
        if rc != 0:
            return None, err or "issue failed"
        return {"issue_url": out.split()[-1] if out else ""}, None

    # ── dispatch ─────────────────────────────────────────────────────────────
    def perform(self, **kwargs):
        action = (kwargs.get("action") or "scan").strip().lower()
        wh, src = self._load(kwargs)

        if action in ("scan", "weakest") and not wh:
            return self._env(action, "error", error="empty warehouse — none to rank. Seed warehouse/moments.json or publish the repo first.")

        if action == "scan":
            r = rank(wh)
            rows = [{"rank": i + 1, "title": m.get("t"), "author": m.get("a"), "biome": m.get("b"),
                     "keyframes": len(m.get("k", [])), "strength": m["_strength"],
                     "play_url": self._play(m)} for i, m in enumerate(r)]
            return self._env(action, "success", warehouse=len(wh), warehouse_source=src,
                             weakest=rows[0]["title"], strongest=rows[-1]["title"], ranking=rows)

        if action == "weakest":
            w = weakest(wh)
            return self._env(action, "success", note="this is the next double-jump target",
                             target=self._card(w))

        if action == "challenge":
            ranked = rank(wh)
            target = ranked[0]
            clean_target = self._moment(target)
            second = ranked[1]["_strength"] if len(ranked) > 1 else target["_strength"]
            bar = round(max(target["_strength"] + 0.05, second), 4)
            revision = "|".join(sorted(moment_id(moment) for moment in wh))
            return self._env(
                action,
                "success",
                challenge_id=moment_id(clean_target) + ":" + str(bar),
                frontier_revision=revision,
                target=self._card(clean_target),
                second_strength=second,
                margin=0.05,
                bar=bar,
                instruction=(
                    "Use the local brainstem's domain intelligence to author one complete Moment child, "
                    "then call action=propose with token=<child> and target_token=<target token>. "
                    "Only the deterministic scorer can accept it."
                ),
            )

        if action == "propose":
            if not kwargs.get("token") or not kwargs.get("target_token"):
                return self._env(action, "error", error="propose needs token=<candidate> and target_token=<challenged parent>.")
            try:
                candidate = decode_token(kwargs["token"])
                target = decode_token(kwargs["target_token"])
            except Exception as e:
                return self._env(action, "error", error=f"bad token: {e}")
            active = next((moment for moment in wh if moment_id(moment) == moment_id(target)), None)
            if active is None:
                return self._env(action, "error", error="challenged parent is no longer on the active frontier.")
            ranked = sorted(wh, key=strength)
            if moment_id(ranked[0]) != moment_id(active):
                return self._env(action, "error", error="challenge is stale; request the current weakest again.")
            second = strength(ranked[1]) if len(ranked) > 1 else strength(active)
            bar = round(max(strength(active) + 0.05, second), 4)
            score = strength(candidate)
            cleared = score >= bar
            return self._env(
                action,
                "accepted" if cleared else "rejected",
                cleared=cleared,
                bar=bar,
                improvement={"from": strength(active), "to": score, "delta": round(score - strength(active), 4)},
                target=self._card(active),
                result=self._card(candidate),
                next=("submit the accepted result token" if cleared else "revise the candidate and propose again"),
            )

        if action == "jump":
            if kwargs.get("token"):
                try:
                    target = decode_token(kwargs["token"])
                except Exception as e:
                    return self._env(action, "error", error=f"bad token: {e}")
                dj = double_jump([target], improve)
            else:
                if not wh:
                    return self._env(action, "error", error="empty warehouse and no token to jump.")
                dj = double_jump(wh, improve)
            imp = dj["improved"]
            if kwargs.get("title"):
                imp["t"] = kwargs["title"]
            return self._env(action, "success", cleared=dj["cleared"],
                             improvement={"from": dj["from"], "to": dj["to"], "bar": dj["bar"],
                                          "delta": round(dj["to"] - dj["from"], 4)},
                             target=self._card(dj["target"]), result=self._card(imp),
                             next="pass result.token to action=submit to publish it")

        if action == "triple_jump":
            pool = wh or [mint(seed=1), mint(seed=2)]
            tj = triple_jump(pool, improve)
            return self._env(action, "success", rounds=tj["rounds"],
                             champion=self._card(tj["champion"], {"won": "the triple jump"}))

        if action == "submit":
            if not kwargs.get("token"):
                return self._env(action, "error", error="action=submit needs token=<Moment share token> (run action=jump first and submit result.token).")
            try:
                m = decode_token(kwargs["token"])
            except Exception as e:
                return self._env(action, "error", error=f"bad token: {e}")
            if new_budget is not None:
                try:
                    new_budget().authorize_side_effect("publish", explicit=True)
                except PolicyViolation as e:
                    return self._env(action, "error", error=str(e), code=getattr(e, "code", "policy_rejected"))
            gist, gerr = self._gist(m)
            if gerr:
                return self._env(action, "error", stage="gist", error=gerr,
                                 hint="ensure `gh auth login` with gist scope.")
            issue, ierr = self._issue(m, gist)
            if ierr:
                return self._env(action, "degraded", stage="issue", error=ierr, gist=gist,
                                 card=self._card(m), hint="gist created; issue failed (repo/label?).")
            return self._env(action, "success", gist=gist, issue=issue, card=self._card(m),
                             note="published as a public gist + opened a moment-submit issue (CRUD create).")

        if action == "loop":
            if not wh:
                return self._env(action, "error", error="empty warehouse to loop over.")
            rounds = int(kwargs.get("rounds") or 1)
            do_submit = bool(kwargs.get("submit"))
            if do_submit and new_budget is not None:
                try:
                    new_budget().authorize_side_effect("publish", explicit=True)
                except PolicyViolation as e:
                    return self._env(action, "error", error=str(e), code=getattr(e, "code", "policy_rejected"))
            pool = [dict(m) for m in wh]
            log = []
            for i in range(rounds):
                dj = double_jump(pool, improve)
                imp = dj["improved"]
                if not dj["cleared"]:
                    log.append({"round": i + 1, "target": dj["target"].get("t"),
                                "from": dj["from"], "to": dj["to"], "cleared": False,
                                "error": "candidate did not clear the objective bar"})
                    break
                target_id = moment_id(dj["target"])
                pool = [moment for moment in pool if moment_id(moment) != target_id] + [imp]
                entry = {"round": i + 1, "target": dj["target"].get("t"),
                         "from": dj["from"], "to": dj["to"], "cleared": dj["cleared"],
                         "result": imp.get("t"), "token": encode_token(imp), "play_url": self._play(imp)}
                if do_submit:
                    gist, gerr = self._gist(imp)
                    issue, ierr = (None, None) if gerr else self._issue(imp, gist)
                    entry["submitted"] = {"gist": gist, "issue": issue, "error": gerr or ierr}
                log.append(entry)
            return self._env(action, "success", rounds=rounds, submitted=do_submit,
                             improved=len(log), log=log,
                             note="autonomous improvement loop complete; warehouse grows append-only.")

        if action == "promote":
            tool = os.path.join(_ROOT, "tools", "promote.py")
            if not os.path.exists(tool):
                return self._env(action, "error",
                                 error="promote tool not found — run this from inside the double-jump cubby repo.")
            args = ["python3", tool]
            if kwargs.get("apply"):
                args.append("--apply")
            rc, out, err = _run(args, timeout=240)        # clone + PR can take a bit
            try:
                res = json.loads(out)
            except Exception:
                res = {"raw": out[:800], "stderr": err[:400]}
            return self._env(action, "success" if rc == 0 else "error",
                             reach_up="global rapp-commons Moment feed (by PR)",
                             dry_run=not bool(kwargs.get("apply")), result=res)

        if action == "resolve":
            tool = os.path.join(_ROOT, "tools", "resolve_card.py")
            if not os.path.exists(tool):
                return self._env(action, "error",
                                 error="resolve tool not found — run this from inside the double-jump cubby repo.")
            args = ["python3", tool]
            if kwargs.get("id"):
                args += ["--id", kwargs["id"]]
            rc, out, err = _run(args, timeout=60)
            try:
                res = json.loads(out)
            except Exception:
                res = {"raw": out[:1000], "stderr": err[:400]}
            return self._env(action, "success" if rc == 0 else "error",
                             note="resolved into an ERC-721/OpenSea token URI; animation_url is the live walkable hologram (zero servers).",
                             result=res)

        return self._env(action, "error", error=f"unknown action '{action}'. Use scan|weakest|challenge|propose|jump|triple_jump|submit|loop|promote|resolve.")
