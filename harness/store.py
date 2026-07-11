"""Append-only evolution events over immutable, content-addressed Moments."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
import os
import tempfile

from .strength import FITNESS_V1, FITNESS_V2, FITNESS_VERSIONS, serialized_components, strength
from .moment import draft_improvements
from .validation import canonical_json, moment_id, validate_moment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAREHOUSE = os.path.join(ROOT, "warehouse", "moments.json")
EVOLUTION = os.path.join(ROOT, "warehouse", "evolution.json")
FRONTIER = os.path.join(ROOT, "warehouse", "frontier.json")
SCHEMA = "double-jump-evolution/2.0"
LEGACY_SCHEMAS = {"double-jump-evolution/1.0", SCHEMA}
FITNESS_VERSION = FITNESS_V1

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


def _related_path(warehouse_path, name):
    if os.path.abspath(warehouse_path) == os.path.abspath(WAREHOUSE):
        return os.path.join(os.path.dirname(warehouse_path), name)
    stem, _ = os.path.splitext(warehouse_path)
    suffix = name.rsplit(".", 1)[-1]
    return f"{stem}.{name.rsplit('.', 1)[0]}.{suffix}"


def _atomic_stable_write(path, document):
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            old = handle.read()
    if old == text:
        return False
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".double-jump-", suffix=".tmp", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def _document_text(document):
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _lock_path(warehouse_path):
    return _related_path(warehouse_path, "writer.lock")


def _journal_path(warehouse_path):
    return _related_path(warehouse_path, "transaction.json")


@contextmanager
def writer_lock(warehouse_path=WAREHOUSE):
    path = _lock_path(warehouse_path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _replace_text(path, text):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".double-jump-txn-", suffix=".tmp", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _recover_transaction(warehouse_path, evolution_path, frontier_path):
    journal_path = _journal_path(warehouse_path)
    if not os.path.exists(journal_path):
        return False
    journal = _read_json(journal_path, None)
    expected = {
        os.path.abspath(warehouse_path),
        os.path.abspath(evolution_path),
        os.path.abspath(frontier_path),
    }
    files = journal.get("files") if isinstance(journal, dict) else None
    if not isinstance(journal, dict) or journal.get("schema") != "double-jump-transaction/1.0" or not isinstance(files, list):
        raise ValueError("invalid warehouse transaction journal")
    if {os.path.abspath(item.get("path", "")) for item in files} != expected:
        raise ValueError("transaction journal contains unexpected paths")
    for item in files:
        if not isinstance(item.get("new"), str):
            raise ValueError("transaction journal contains invalid staged content")
        _replace_text(item["path"], item["new"])
    os.unlink(journal_path)
    return True


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _jump_id(parent_id, child_id, fitness_version=FITNESS_VERSION):
    key = f"{fitness_version}|{parent_id}|{child_id}"
    return "jump:" + hashlib.sha256(key.encode("utf-8")).hexdigest()


def _event_hash(event):
    payload = {key: value for key, value in event.items() if key != "hash"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _upgrade_events(events, moments, legacy=False):
    by_id = {moment_id(moment): moment for moment in moments}
    upgraded, previous = [], None
    for raw_event in events:
        if not isinstance(raw_event, dict):
            raise ValueError("evolution events must be objects")
        event = dict(raw_event)
        if event.get("type") == "accepted_jump":
            parent_id, child_id = event.get("parent"), event.get("child")
            if parent_id not in by_id or child_id not in by_id:
                raise ValueError("evolution event references an unknown Moment")
            fitness_version = event.get("fitness") or FITNESS_VERSION
            if fitness_version not in FITNESS_VERSIONS:
                raise ValueError(f"unknown evolution fitness version: {fitness_version}")
            expected_id = _jump_id(parent_id, child_id, fitness_version)
            if event.get("id", expected_id) != expected_id:
                raise ValueError("evolution event id does not match its transition")
            event["id"] = expected_id
            event["fitness"] = fitness_version
            expected_from = strength(by_id[parent_id], fitness_version)
            expected_to = strength(by_id[child_id], fitness_version)
            if not legacy and event.get("from") != expected_from:
                raise ValueError("evolution event parent score does not verify")
            if not legacy and event.get("to") != expected_to:
                raise ValueError("evolution event child score does not verify")
            event["from"] = expected_from
            event["to"] = expected_to
            event["bar"] = round(float(event["bar"]), 4)
            event["improver"] = str(event.get("improver") or "unknown")
            event["rationale"] = str(event.get("rationale") or "")
            event["provenance"] = dict(event.get("provenance") or {})
        elif event.get("type") == "tombstone":
            if event.get("target") not in by_id:
                raise ValueError("tombstone references an unknown Moment")
        else:
            raise ValueError(f"unknown evolution event type: {event.get('type')}")
        if (not legacy and "previous" not in event) or event.get("previous", previous) != previous:
            raise ValueError("evolution event hash chain is broken")
        event["previous"] = previous
        expected_hash = _event_hash(event)
        if (not legacy and "hash" not in event) or event.get("hash", expected_hash) != expected_hash:
            raise ValueError("evolution event hash does not verify")
        event["hash"] = expected_hash
        upgraded.append(event)
        previous = expected_hash
    return upgraded


@dataclass
class EvolutionState:
    moments: list
    events: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    warehouse_path: str = WAREHOUSE
    evolution_path: str = EVOLUTION
    frontier_path: str = FRONTIER
    base_revision: str = None

    @property
    def by_id(self):
        return {moment_id(moment): moment for moment in self.moments}

    @property
    def active_ids(self):
        roots = self.meta.get("roots")
        if roots is None:
            active = set(self.by_id)
        else:
            if not isinstance(roots, list) or any(identifier not in self.by_id for identifier in roots):
                raise ValueError("evolution roots must reference known Moments")
            active = set(roots)
        seen_events = set()
        previous = None
        for event in self.events:
            event_id = event.get("id")
            if not event_id or event_id in seen_events:
                raise ValueError("evolution events must have unique ids")
            seen_events.add(event_id)
            kind = event.get("type")
            if kind == "accepted_jump":
                parent, child = event.get("parent"), event.get("child")
                if parent not in self.by_id or child not in self.by_id:
                    raise ValueError("evolution event references an unknown Moment")
                if parent not in active:
                    raise ValueError("evolution event targets a retired Moment")
                fitness_version = event.get("fitness")
                if fitness_version not in FITNESS_VERSIONS:
                    raise ValueError("unknown evolution fitness version")
                if event.get("from") != strength(self.by_id[parent], fitness_version):
                    raise ValueError("evolution event parent score does not verify")
                if event.get("to") != strength(self.by_id[child], fitness_version):
                    raise ValueError("evolution event child score does not verify")
                if event["to"] < event.get("bar", float("inf")):
                    raise ValueError("evolution event child did not clear its recorded bar")
                if not (event.get("provenance") or {}).get("retain_parent"):
                    active.discard(parent)
                active.add(child)
            elif kind == "tombstone":
                target = event.get("target")
                if target not in self.by_id:
                    raise ValueError("tombstone references an unknown Moment")
                active.discard(target)
            else:
                raise ValueError(f"unknown evolution event type: {kind}")
            if event.get("previous") != previous or event.get("hash") != _event_hash(event):
                raise ValueError("evolution event hash chain does not verify")
            previous = event["hash"]
        return active

    @property
    def active_moments(self):
        ids = self.active_ids
        return [moment for moment in self.moments if moment_id(moment) in ids]

    @property
    def revision(self):
        payload = {
            "artifacts": sorted(self.by_id),
            "events": self.events,
            "meta": self.meta,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def unique_moments(moments):
    out, seen = [], set()
    for moment in moments:
        validate_moment(moment)
        identifier = moment_id(moment)
        if identifier not in seen:
            seen.add(identifier)
            out.append(moment)
    return out


def _load_state_unlocked(warehouse_path=WAREHOUSE, evolution_path=None, frontier_path=None):
    evolution_path = evolution_path or _related_path(warehouse_path, "evolution.json")
    frontier_path = frontier_path or _related_path(warehouse_path, "frontier.json")
    warehouse = _read_json(warehouse_path, {"moments": []})
    raw_moments = warehouse.get("moments", warehouse if isinstance(warehouse, list) else [])
    if not isinstance(raw_moments, list):
        raise ValueError("warehouse must contain a moments array")
    ledger = _read_json(evolution_path, {"schema": SCHEMA, "meta": {}, "events": []})
    if ledger.get("schema") not in LEGACY_SCHEMAS or not isinstance(ledger.get("events"), list):
        raise ValueError(f"evolution ledger must use a supported schema")
    moments = unique_moments(raw_moments)
    state = EvolutionState(
        moments=moments,
        events=_upgrade_events(ledger["events"], moments, legacy=ledger.get("schema") != SCHEMA),
        meta=dict(ledger.get("meta") or {}),
        warehouse_path=warehouse_path,
        evolution_path=evolution_path,
        frontier_path=frontier_path,
    )
    state.active_ids
    state.base_revision = state.revision
    return state


def load_state(warehouse_path=WAREHOUSE, evolution_path=None, frontier_path=None):
    evolution_path = evolution_path or _related_path(warehouse_path, "evolution.json")
    frontier_path = frontier_path or _related_path(warehouse_path, "frontier.json")
    with writer_lock(warehouse_path):
        _recover_transaction(warehouse_path, evolution_path, frontier_path)
        return _load_state_unlocked(warehouse_path, evolution_path, frontier_path)


def acceptance_event(parent, child, bar, improver, rationale=None, created_at=None,
                     provenance=None, previous=None, fitness_version=FITNESS_VERSION):
    parent_id, child_id = moment_id(parent), moment_id(child)
    if fitness_version not in FITNESS_VERSIONS:
        raise ValueError(f"unknown fitness version: {fitness_version}")
    from_score, to_score = strength(parent, fitness_version), strength(child, fitness_version)
    if to_score < bar:
        raise ValueError(f"candidate strength {to_score} did not clear bar {bar}")
    event = {
        "id": _jump_id(parent_id, child_id, fitness_version),
        "type": "accepted_jump",
        "parent": parent_id,
        "child": child_id,
        "from": from_score,
        "to": to_score,
        "bar": round(bar, 4),
        "fitness": fitness_version,
        "improver": improver,
        "rationale": rationale or "",
        "provenance": provenance or {},
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "previous": previous,
    }
    event["hash"] = _event_hash(event)
    return event


def accept_jump(state, parent, child, bar, improver="deterministic", rationale=None, created_at=None,
                allow_existing_child=False, provenance=None, fitness_version=FITNESS_VERSION,
                retain_parent=False):
    validate_moment(parent)
    validate_moment(child)
    parent_id, child_id = moment_id(parent), moment_id(child)
    if parent_id not in state.active_ids:
        raise ValueError("jump target is not on the active frontier")
    if parent_id == child_id:
        return False, "duplicate"
    if child_id in state.by_id and not allow_existing_child:
        return False, "duplicate"
    previous = state.events[-1]["hash"] if state.events else None
    provenance = dict(provenance or {})
    if retain_parent:
        provenance["retain_parent"] = True
    event = acceptance_event(
        parent,
        child,
        bar,
        improver,
        rationale,
        created_at,
        provenance,
        previous,
        fitness_version,
    )
    if any(existing.get("id") == event["id"] for existing in state.events):
        return False, "duplicate"
    if child_id not in state.by_id:
        state.moments.append(child)
    state.events.append(event)
    state.active_ids
    return True, "accepted"


def frontier_document(state):
    from .diversity import archive_document, niche

    active = sorted(state.active_moments, key=strength)
    entries = [
        {
            "id": moment_id(moment),
            "strength": strength(moment),
            "fitness": {
                FITNESS_V1: strength(moment, FITNESS_V1),
                FITNESS_V2: strength(moment, FITNESS_V2),
            },
            "components": serialized_components(moment),
            "niche": niche(moment, FITNESS_V1),
            "moment": moment,
        }
        for moment in active
    ]
    draft_document = None
    if active:
        target = active[0]
        second = strength(active[1]) if len(active) > 1 else strength(target)
        bar = round(max(strength(target) + 0.05, second), 4)
        draft_document = {
            "target_id": moment_id(target),
            "bar": bar,
            "profiles": [
                {
                    "profile": profile,
                    "id": moment_id(moment),
                    "strength": strength(moment, FITNESS_V1),
                    "strength_v2": strength(moment, FITNESS_V2),
                    "cleared": strength(moment, FITNESS_V1) >= bar,
                    "components": serialized_components(moment, FITNESS_V1),
                    "moment": moment,
                }
                for profile, moment in draft_improvements(target)
            ],
        }
    return {
        "schema": "double-jump-frontier/1.0",
        "revision": state.revision,
        "observations": state.meta.get("legacy_observations", len(state.moments)),
        "artifacts": len(state.moments),
        "active": len(active),
        "retired": len(state.moments) - len(active),
        "floor": entries[0]["strength"] if entries else None,
        "champion": entries[-1]["id"] if entries else None,
        "draft": draft_document,
        "quality_diversity": archive_document(active, FITNESS_V1),
        "entries": entries,
    }


def save_state(state, operation_id=None):
    if "roots" not in state.meta:
        accepted_children = {
            event["child"] for event in state.events
            if event.get("type") == "accepted_jump"
        }
        state.meta["roots"] = sorted(set(state.by_id) - accepted_children)
    documents = (
        (state.warehouse_path, {"moments": unique_moments(state.moments)}),
        (state.evolution_path, {"schema": SCHEMA, "meta": state.meta, "events": state.events}),
        (state.frontier_path, frontier_document(state)),
    )
    with writer_lock(state.warehouse_path):
        _recover_transaction(state.warehouse_path, state.evolution_path, state.frontier_path)
        current = _load_state_unlocked(state.warehouse_path, state.evolution_path, state.frontier_path)
        if state.base_revision is not None and current.revision != state.base_revision:
            raise RuntimeError("stale warehouse revision; reload and recompute the mutation")
        files = []
        for path, document in documents:
            new = _document_text(document)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    old = handle.read()
            else:
                old = None
            files.append({"path": os.path.abspath(path), "old": old, "new": new})
        if all(item["old"] == item["new"] for item in files):
            return False
        journal = {
            "schema": "double-jump-transaction/1.0",
            "operation_id": operation_id or (state.events[-1]["id"] if state.events else state.revision),
            "base_revision": state.base_revision,
            "target_revision": state.revision,
            "files": files,
        }
        _atomic_stable_write(_journal_path(state.warehouse_path), journal)
        fault_after = int(os.environ.get("DOUBLE_JUMP_FAULT_AFTER_REPLACE", "0") or 0)
        for index, item in enumerate(files, 1):
            _replace_text(item["path"], item["new"])
            if fault_after == index:
                raise RuntimeError(f"injected transaction fault after replace {index}")
        os.unlink(_journal_path(state.warehouse_path))
        state.base_revision = state.revision
        return True
