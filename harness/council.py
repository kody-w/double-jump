"""Exact-eight product strategy council with deterministic consensus receipts."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import tempfile

from .brainstem import BrainstemError

STRATEGIES = (
    ("evolution", "evolution mechanics, lineage, provenance, and sustained frontier progress"),
    ("orchestration", "local brainstem and GitHub Copilot CLI orchestration, consensus, and bounded autonomy"),
    ("trust", "trust boundaries, security, permissions, provenance, and fail-closed behavior"),
    ("game", "player agency, game systems, progression, competition, and replayability"),
    ("experience", "UX, accessibility, mobile behavior, frontend performance, and observability"),
    ("fitness", "fitness integrity, Goodhart resistance, novelty, diversity, and explainability"),
    ("reliability", "tests, transactions, recovery, CI, scheduling, telemetry, and operations"),
    ("product", "product coherence, differentiation, onboarding, federation, and sustainable scope"),
)
SCHEMA = "double-jump-council/1.0"
CONSENSUS_VERSION = "double-jump-consensus/2.0"
STOP_WORDS = {
    "a", "an", "and", "for", "of", "the", "to", "with", "safe", "deterministic",
    "versioned", "double", "jump", "v1", "v2",
}
TOKEN_ALIASES = {
    "versioned": "version",
    "versioning": "version",
    "profiles": "version",
    "profile": "version",
    "epochs": "version",
    "calibration": "version",
    "rescoring": "version",
    "novelty": "diversity",
    "speciation": "diversity",
    "pareto": "diversity",
    "archive": "diversity",
    "interactive": "builder",
    "guided": "builder",
    "browser": "builder",
    "builder": "builder",
    "resumable": "durability",
    "atomic": "durability",
    "transactions": "durability",
    "concurrency": "durability",
    "scheduled": "durability",
    "signed": "trust",
    "trustworthy": "trust",
    "federation": "trust",
}
CONCEPT_TOKENS = {"diversity", "builder", "durability"}


class CouncilConsensusError(BrainstemError):
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _git(root, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def repository_snapshot(root):
    readme_path = os.path.join(root, "README.md")
    frontier_path = os.path.join(root, "warehouse", "frontier.json")
    readme = open(readme_path, encoding="utf-8").read()[:8000] if os.path.exists(readme_path) else ""
    frontier = {}
    if os.path.exists(frontier_path):
        with open(frontier_path, encoding="utf-8") as handle:
            raw = json.load(handle)
        frontier = {
            key: raw.get(key)
            for key in ("schema", "revision", "observations", "artifacts", "active", "retired", "floor", "champion")
        }
    snapshot = {
        "schema": "double-jump-council-snapshot/1.0",
        "repository": "kody-w/double-jump",
        "head": _git(root, "rev-parse", "HEAD"),
        "status": _git(root, "status", "--short")[:12000],
        "diff_stat": _git(root, "diff", "--stat")[:12000],
        "frontier": frontier,
        "readme": readme,
    }
    snapshot["digest"] = _digest(snapshot)
    return snapshot


def strategy_prompt(strategy_id, lens, snapshot, completed_features=()):
    return (
        "You are one independent member of an exact-eight Double Jump product council. "
        f"Your strategy ID is `{strategy_id}` and your lens is: {lens}. "
        "Analyze the immutable repository snapshot below. Do not call tools and do not infer peer votes. "
        "Do not re-propose completed features. Return exactly one JSON object with exactly `strategy_id` "
        "and `proposals`. `proposals` must contain exactly five ranked objects with exactly: feature_id "
        "(stable kebab-case), title, priority (integer 0-100), scope (S, M, or L), rationale, files "
        "(nonempty array of repository-relative paths), and acceptance (nonempty array of testable strings). "
        "Use the most obvious domain-level feature_id so independently similar ideas converge. No markdown "
        "or extra text.\n\nCOMPLETED FEATURES:\n"
        + json.dumps(list(completed_features), ensure_ascii=False)
        + "\n\nSNAPSHOT:\n"
        + json.dumps(snapshot, ensure_ascii=False)
    )


def validate_ballot(value, strategy_id):
    if not isinstance(value, dict) or set(value) != {"strategy_id", "proposals"}:
        raise BrainstemError(f"{strategy_id} ballot has an invalid envelope")
    if value["strategy_id"] != strategy_id:
        raise BrainstemError(f"{strategy_id} ballot echoed the wrong strategy")
    proposals = value["proposals"]
    if not isinstance(proposals, list) or len(proposals) != 5:
        raise BrainstemError(f"{strategy_id} ballot must contain exactly five proposals")
    required = {"feature_id", "title", "priority", "scope", "rationale", "files", "acceptance"}
    seen = set()
    for rank, proposal in enumerate(proposals, 1):
        if not isinstance(proposal, dict) or set(proposal) != required:
            raise BrainstemError(f"{strategy_id} proposal {rank} has invalid fields")
        feature_id = proposal["feature_id"]
        if not isinstance(feature_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", feature_id):
            raise BrainstemError(f"{strategy_id} proposal {rank} has an invalid feature_id")
        if feature_id in seen:
            raise BrainstemError(f"{strategy_id} ballot repeats feature_id {feature_id}")
        seen.add(feature_id)
        if not isinstance(proposal["priority"], int) or not 0 <= proposal["priority"] <= 100:
            raise BrainstemError(f"{strategy_id} proposal {rank} has an invalid priority")
        if proposal["scope"] not in {"S", "M", "L"}:
            raise BrainstemError(f"{strategy_id} proposal {rank} has an invalid scope")
        for field in ("title", "rationale"):
            if not isinstance(proposal[field], str) or not proposal[field].strip():
                raise BrainstemError(f"{strategy_id} proposal {rank} has an empty {field}")
        for field in ("files", "acceptance"):
            if not isinstance(proposal[field], list) or not proposal[field] or not all(
                isinstance(item, str) and item.strip() for item in proposal[field]
            ):
                raise BrainstemError(f"{strategy_id} proposal {rank} has an invalid {field}")
    return value


def _text_tokens(text):
    return frozenset(
        TOKEN_ALIASES.get(token, token)
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 2
    )


def _tokens(proposal):
    return _text_tokens(proposal["feature_id"].replace(".", " ") + " " + proposal["title"])


def _similarity(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _cluster_score(left, right):
    shared = left & right
    if len(shared) >= 2:
        return 2 + _similarity(left, right)
    if shared & CONCEPT_TOKENS:
        return 1 + _similarity(left, right)
    return 0.0


def consensus(ballots):
    strategy_order = {strategy_id: index for index, (strategy_id, _) in enumerate(STRATEGIES)}
    ordered = []
    for ballot in ballots:
        strategy_id = ballot["strategy_id"]
        for rank, proposal in enumerate(ballot["proposals"], 1):
            ordered.append((strategy_order[strategy_id], strategy_id, rank, proposal))
    ordered.sort(key=lambda row: (row[0], row[2], row[3]["feature_id"]))

    clusters = []
    for _, strategy_id, rank, proposal in ordered:
        tokens = _tokens(proposal)
        candidates = [
            (_cluster_score(tokens, cluster["tokens"]), index)
            for index, cluster in enumerate(clusters)
        ]
        score, index = max(candidates, default=(0.0, -1), key=lambda item: (item[0], -item[1]))
        if score == 0:
            clusters.append({"tokens": tokens, "members": []})
            index = len(clusters) - 1
        clusters[index]["tokens"] = clusters[index]["tokens"] | tokens
        clusters[index]["members"].append({
            "strategy_id": strategy_id,
            "rank": rank,
            "feature_id": proposal["feature_id"],
            "title": proposal["title"],
            "priority": proposal["priority"],
            "scope": proposal["scope"],
        })

    ranked = []
    for cluster in clusters:
        members = cluster["members"]
        strategies = {member["strategy_id"] for member in members}
        representative = sorted(
            members,
            key=lambda member: (-member["priority"], member["rank"], member["feature_id"]),
        )[0]
        ranked.append({
            "canonical_feature": representative["feature_id"],
            "title": representative["title"],
            "support": len(strategies),
            "average_priority": round(sum(member["priority"] for member in members) / len(members), 2),
            "borda": sum(6 - member["rank"] for member in members),
            "best_rank": min(member["rank"] for member in members),
            "members": sorted(members, key=lambda member: (member["strategy_id"], member["rank"])),
        })
    ranked.sort(key=lambda item: (
        -item["support"],
        -item["average_priority"],
        -item["borda"],
        item["best_rank"],
        item["canonical_feature"],
    ))
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return ranked


def run_council(provider, snapshot, completed_features=(), created_at=None, budget=None):
    ballots = {}
    errors = {}

    def run_one(strategy_id, lens):
        if budget is not None:
            budget.consume_council()
        prompt = strategy_prompt(strategy_id, lens, snapshot, completed_features)
        return validate_ballot(provider.complete_json(prompt), strategy_id)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(run_one, strategy_id, lens): strategy_id
            for strategy_id, lens in STRATEGIES
        }
        for future in as_completed(futures):
            strategy_id = futures[future]
            try:
                ballots[strategy_id] = future.result()
            except Exception as exc:
                errors[strategy_id] = str(exc)
    if errors or len(ballots) != 8:
        raise BrainstemError(f"council failed closed: {errors}")

    ordered_ballots = [ballots[strategy_id] for strategy_id, _ in STRATEGIES]
    ranking = consensus(ordered_ballots)
    completed_tokens = [_text_tokens(feature.replace(".", " ")) for feature in completed_features]
    supported = [
        item for item in ranking
        if item["support"] >= 2
        and not any(
            _cluster_score(
                frozenset(token for member in item["members"] for token in _text_tokens(member["feature_id"])),
                done,
            )
            for done in completed_tokens
        )
    ]
    receipt = {
        "schema": SCHEMA,
        "consensus_version": CONSENSUS_VERSION,
        "status": "complete" if len(supported) >= 3 else "insufficient_consensus",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "snapshot_digest": snapshot["digest"],
        "completed_features": sorted(set(completed_features)),
        "strategies": [
            {
                "strategy_id": ballot["strategy_id"],
                "ballot_hash": _digest(ballot),
                "proposals": ballot["proposals"],
            }
            for ballot in ordered_ballots
        ],
        "ranking": ranking,
        "top_three": [item["canonical_feature"] for item in supported[:3]],
        "budget": budget.receipt() if budget is not None else None,
    }
    receipt["cycle_id"] = _digest({key: value for key, value in receipt.items() if key != "created_at"})
    if len(supported) < 3:
        raise CouncilConsensusError(
            "council failed closed: fewer than three independently supported features",
            receipt,
        )
    return receipt


def write_receipt(root, receipt):
    cycles_dir = os.path.join(root, "council", "cycles")
    os.makedirs(cycles_dir, exist_ok=True)
    slug = receipt["cycle_id"].split(":", 1)[1]
    path = os.path.join(cycles_dir, slug + ".json")
    text = json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            if handle.read() != text:
                raise ValueError("cycle receipt id collision")
    else:
        fd, temporary = tempfile.mkstemp(prefix=".council-", suffix=".tmp", dir=cycles_dir, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    receipts = []
    failure_dir = os.path.join(root, "council", "failures")
    for directory, prefix in ((cycles_dir, "council/cycles"), (failure_dir, "council/failures")):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                value = json.load(handle)
            receipts.append({
                "cycle_id": value["cycle_id"],
                "label": value.get("label") or "CLI council · " + value["cycle_id"].split(":")[-1][:10],
                "created_at": value["created_at"],
                "snapshot_digest": value["snapshot_digest"],
                "status": value.get("status") or "complete",
                "top_three": value["top_three"],
                "url": prefix + "/" + name,
            })
    receipts.sort(key=lambda item: (item["created_at"], item["cycle_id"]), reverse=True)
    index_path = os.path.join(root, "council", "index.json")
    index_text = json.dumps(
        {"schema": "double-jump-council-index/1.0", "cycles": receipts},
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(index_text)
    return path
