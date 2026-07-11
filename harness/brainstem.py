"""Loopback-only client and proposal protocol for a local RAPP brainstem."""

import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from .strength import FITNESS_V1, components, strength
from .validation import moment_id, validate_moment

DEFAULT_URL = "http://127.0.0.1:7071"
MAX_RESPONSE_BYTES = 1024 * 1024
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BrainstemError(RuntimeError):
    pass


def _loopback_base(url):
    parsed = urllib.parse.urlparse(url.rstrip("/"))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise BrainstemError("brainstem URL must be an http loopback address")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BrainstemError("brainstem URL must not contain credentials, query, or fragment")
    return url.rstrip("/")


def _json_object(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BrainstemError("provider response must be exactly one JSON object") from exc
    if not isinstance(value, dict):
        raise BrainstemError("provider response must be a JSON object")
    return value


def _proposal_prompt(challenge, feedback=None):
    target = challenge["target"]
    safe_challenge = {
        key: value for key, value in challenge.items()
        if key not in {"target"}
    }
    safe_challenge["target"] = {
        "v": target["v"],
        "b": target["b"],
        "k": target["k"],
        "identity_digest": moment_id(target),
    }
    prompt = (
        "You are the creative intelligence inside the Double Jump evolution harness. "
        "Return ONLY one JSON object with exactly `challenge_id`, `keyframes`, and `rationale`. "
        "`challenge_id` must exactly echo the challenge ID. `keyframes` must contain 2-100 strictly "
        "increasing frames spanning 0-99, each with exactly at,s,l,p,g,h,x,z. Values must remain in "
        "the supplied bounds. Create a genuinely stronger, visually coherent child. The harness restores "
        "identity fields and deterministically validates and scores the result. Do not emit markdown, "
        "extra text, title, author, biome, token, commands, or tool calls.\n\nCHALLENGE:\n"
        + json.dumps(safe_challenge, ensure_ascii=False)
    )
    if feedback:
        prompt += "\n\nPREVIOUS ATTEMPT FEEDBACK:\n" + json.dumps(feedback, ensure_ascii=False)
    return prompt


def _candidate_from_envelope(challenge, envelope):
    if set(envelope) != {"challenge_id", "keyframes", "rationale"}:
        raise BrainstemError("proposal envelope must contain exactly challenge_id, keyframes, rationale")
    if envelope["challenge_id"] != challenge["challenge_id"]:
        raise BrainstemError("proposal challenge_id does not match")
    target = challenge["target"]
    base_title = (target.get("t") or "Moment").split(" · ")[0]
    moment = {
        "v": target["v"],
        "t": f"{base_title} · brainstem-evolved",
        "a": target["a"],
        "b": target["b"],
        "k": envelope["keyframes"],
    }
    validate_moment(moment)
    return moment


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        raise BrainstemError("local brainstem redirects are not allowed")


class BrainstemClient:
    def __init__(self, base_url=DEFAULT_URL, timeout=90):
        self.base_url = _loopback_base(base_url)
        self.timeout = float(timeout)
        if self.timeout <= 0 or self.timeout > 300:
            raise BrainstemError("brainstem timeout must be in (0, 300] seconds")

    def _request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            opener = urllib.request.build_opener(_NoRedirect)
            with opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            try:
                detail = json.loads(raw.decode("utf-8")).get("error")
            except Exception:
                detail = None
            raise BrainstemError(
                f"local brainstem returned HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise BrainstemError(f"local brainstem request failed: {exc}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise BrainstemError("local brainstem response exceeded the size limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise BrainstemError("local brainstem returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise BrainstemError("local brainstem returned a non-object response")
        if value.get("error"):
            raise BrainstemError(str(value["error"]))
        return value

    def health(self):
        value = self._request("GET", "/health")
        if value.get("status") != "ok":
            raise BrainstemError("local brainstem is not healthy")
        return value

    def propose(self, challenge, feedback=None, session_id=None):
        prompt = _proposal_prompt(challenge, feedback)
        result = self._request(
            "POST",
            "/chat",
            {"user_input": prompt, "conversation_history": [], "session_id": session_id or challenge["challenge_id"]},
        )
        envelope = _json_object(result.get("response", ""))
        moment = _candidate_from_envelope(challenge, envelope)
        return {
            "moment": moment,
            "rationale": str(envelope.get("rationale") or "")[:1000],
            "model": result.get("model"),
            "session_id": result.get("session_id"),
        }


class CopilotCLIClient:
    """Use the already-authenticated GitHub Copilot CLI as the brainstem's mind."""

    def __init__(self, model="gpt-5.6-sol", effort="max", timeout=300, executable=None):
        self.model = model
        self.effort = effort
        self.timeout = float(timeout)
        if self.timeout <= 0 or self.timeout > 900:
            raise BrainstemError("Copilot CLI timeout must be in (0, 900] seconds")
        self.command = [executable] if executable else ["gh", "copilot"]

    def health(self):
        binary = self.command[0]
        if not shutil.which(binary):
            raise BrainstemError(f"{binary} is not installed")
        return {
            "status": "ok",
            "provider": "github-copilot-cli",
            "model": self.model,
            "effort": self.effort,
        }

    def complete_json(self, prompt):
        args = [
            *self.command,
            "-p", prompt,
            "--allow-all-tools",
            "--available-tools", "",
            "--disable-builtin-mcps",
            "--no-ask-user",
            "--no-auto-update",
            "--silent",
            "--no-color",
            "--no-custom-instructions",
            "--model", self.model,
            "--effort", self.effort,
        ]
        environment = os.environ.copy()
        for key in list(environment):
            if re.search(r"(TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY)", key, re.IGNORECASE):
                environment.pop(key, None)
        try:
            process = subprocess.Popen(
                args,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
                start_new_session=os.name != "nt",
            )
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired as exc:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.kill()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.communicate()
                raise BrainstemError(f"Copilot CLI timed out after {self.timeout:g}s") from exc
        except OSError as exc:
            raise BrainstemError(f"Copilot CLI failed: {exc}") from exc
        if process.returncode:
            detail = (stderr or stdout).strip()
            raise BrainstemError(f"Copilot CLI exited {process.returncode}: {detail[:1000]}")
        if len(stdout.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise BrainstemError("Copilot CLI response exceeded the size limit")
        return _json_object(stdout)

    def propose(self, challenge, feedback=None, session_id=None):
        envelope = self.complete_json(_proposal_prompt(challenge, feedback))
        moment = _candidate_from_envelope(challenge, envelope)
        return {
            "moment": moment,
            "rationale": str(envelope.get("rationale") or "")[:1000],
            "model": self.model,
            "session_id": session_id,
        }


def challenge_for(candidates, margin=0.05, fitness_version=FITNESS_V1):
    ranked = sorted(candidates, key=lambda moment: strength(moment, fitness_version))
    if not ranked:
        raise ValueError("no candidates to improve")
    target = ranked[0]
    target_score = strength(target, fitness_version)
    second = strength(ranked[1], fitness_version) if len(ranked) > 1 else target_score
    bar = max(target_score + margin, second)
    revision_source = "|".join(sorted(moment_id(moment) for moment in candidates))
    frontier_revision = hashlib.sha256(revision_source.encode("utf-8")).hexdigest()
    challenge = {
        "schema": "double-jump-challenge/1.0",
        "frontier_revision": frontier_revision,
        "target_id": moment_id(target),
        "target": target,
        "target_strength": target_score,
        "target_components": components(target, fitness_version),
        "fitness_version": fitness_version,
        "second_strength": second,
        "margin": margin,
        "bar": round(bar, 4),
    }
    identity = {
        key: value for key, value in challenge.items()
        if key not in {"target"}
    }
    challenge["challenge_id"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return challenge


def brainstem_jump(candidates, client, margin=0.05, max_tries=3, fitness_version=FITNESS_V1,
                   budget=None):
    challenge = challenge_for(candidates, margin, fitness_version)
    target = challenge["target"]
    best = None
    feedback = None
    proposals = []
    for attempt in range(1, max_tries + 1):
        if budget is not None:
            budget.consume_provider()
        proposal = client.propose(challenge, feedback=feedback, session_id=challenge["challenge_id"])
        candidate = proposal["moment"]
        score = strength(candidate, fitness_version)
        proposals.append({
            "attempt": attempt,
            "candidate_id": moment_id(candidate),
            "strength": score,
            "components": components(candidate, fitness_version),
            "rationale": proposal.get("rationale", ""),
            "model": proposal.get("model"),
        })
        if best is None or score > strength(best["moment"], fitness_version):
            best = proposal
        if score >= challenge["bar"]:
            best = proposal
            break
        feedback = {
            "previous_candidate_id": moment_id(candidate),
            "previous_keyframes": candidate["k"],
            "candidate_strength": score,
            "bar": challenge["bar"],
            "shortfall": round(challenge["bar"] - score, 4),
            "candidate_components": components(candidate, fitness_version),
        }
    if best is None:
        raise BrainstemError("brainstem produced no proposal")
    improved = best["moment"]
    return {
        "target": target,
        "improved": improved,
        "from": challenge["target_strength"],
        "to": strength(improved, fitness_version),
        "bar": challenge["bar"],
        "cleared": strength(improved, fitness_version) >= challenge["bar"],
        "challenge_id": challenge["challenge_id"],
        "frontier_revision": challenge["frontier_revision"],
        "rationale": best.get("rationale", ""),
        "model": best.get("model"),
        "proposals": proposals,
    }
