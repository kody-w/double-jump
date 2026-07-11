"""Strict validation and content identity for RAPP Moments."""

import base64
import hashlib
import json
import math
import re

BIOMES = frozenset({"savanna", "canyon", "forest", "volcanic", "void"})
FRAME_FIELDS = frozenset({"at", "s", "l", "p", "g", "h", "x", "z"})
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_TOKEN_CHARS = 65536
MAX_JSON_BYTES = 49152
MAX_TEXT_CHARS = 160
MAX_KEYFRAMES = 100


class MomentValidationError(ValueError):
    """Raised when a value is not a canonical, safe Moment."""


def _number(value, label, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MomentValidationError(f"{label} must be a number")
    if not math.isfinite(value) or not lo <= value <= hi:
        raise MomentValidationError(f"{label} must be finite and in [{lo}, {hi}]")


def _text(value, label):
    if not isinstance(value, str):
        raise MomentValidationError(f"{label} must be a string")
    if not value.strip() or len(value) > MAX_TEXT_CHARS:
        raise MomentValidationError(f"{label} must contain 1-{MAX_TEXT_CHARS} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise MomentValidationError(f"{label} contains control characters")


def validate_moment(moment):
    """Validate a Moment and return it unchanged."""
    if not isinstance(moment, dict):
        raise MomentValidationError("Moment must be a JSON object")
    required = {"v", "t", "a", "b", "k"}
    if set(moment) != required:
        missing = sorted(required - set(moment))
        extra = sorted(set(moment) - required)
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if extra:
            detail.append(f"unknown {extra}")
        raise MomentValidationError(f"Moment has invalid fields ({'; '.join(detail)})")
    if isinstance(moment["v"], bool) or moment["v"] != 1:
        raise MomentValidationError("v must equal 1")
    _text(moment["t"], "t")
    _text(moment["a"], "a")
    if moment["b"] not in BIOMES:
        raise MomentValidationError(f"b must be one of: {', '.join(sorted(BIOMES))}")

    frames = moment["k"]
    if not isinstance(frames, list) or not 2 <= len(frames) <= MAX_KEYFRAMES:
        raise MomentValidationError(f"k must contain 2-{MAX_KEYFRAMES} keyframes")
    previous = -1
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise MomentValidationError(f"k[{index}] must be an object")
        if set(frame) != FRAME_FIELDS:
            missing_fields = sorted(FRAME_FIELDS - set(frame))
            extra_fields = sorted(set(frame) - FRAME_FIELDS)
            detail = []
            if missing_fields:
                detail.append(f"missing {missing_fields}")
            if extra_fields:
                detail.append(f"unknown {extra_fields}")
            raise MomentValidationError(f"k[{index}] has invalid fields ({'; '.join(detail)})")
        at = frame["at"]
        if isinstance(at, bool) or not isinstance(at, int) or not 0 <= at <= 99:
            raise MomentValidationError(f"k[{index}].at must be an integer in [0, 99]")
        if at <= previous:
            raise MomentValidationError("keyframe at values must be strictly increasing")
        previous = at
        for field in ("s", "l", "p", "g"):
            _number(frame[field], f"k[{index}].{field}", 0, 1)
        _number(frame["h"], f"k[{index}].h", 0, 360)
        for field in ("x", "z"):
            _number(frame[field], f"k[{index}].{field}", -1, 1)
    if frames[0]["at"] != 0 or frames[-1]["at"] != 99:
        raise MomentValidationError("keyframes must span at=0 through at=99")
    return moment


def _object_without_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise MomentValidationError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _reject_constant(value):
    raise MomentValidationError(f"non-finite JSON number: {value}")


def decode_token(token):
    """Decode and validate a strict base64url Moment token."""
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_CHARS:
        raise MomentValidationError(f"token must contain 1-{MAX_TOKEN_CHARS} characters")
    if not TOKEN_RE.fullmatch(token):
        raise MomentValidationError("token is not unpadded base64url")
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise MomentValidationError("token is not valid base64url") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise MomentValidationError(f"decoded Moment exceeds {MAX_JSON_BYTES} bytes")
    try:
        moment = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except MomentValidationError:
        raise
    except Exception as exc:
        raise MomentValidationError("token does not contain valid UTF-8 JSON") from exc
    return validate_moment(moment)


def canonical_json(moment):
    """Return stable semantic JSON used for content identity."""
    validate_moment(moment)
    return json.dumps(
        moment,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def moment_id(moment):
    digest = hashlib.sha256(canonical_json(moment).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
