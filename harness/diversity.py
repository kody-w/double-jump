"""Deterministic behavior descriptors and a bounded quality-diversity archive."""

import math

from .strength import FITNESS_V1, components, strength
from .validation import moment_id

QUALITY_FLOOR = 0.20
MIN_NOVELTY = 0.03


def descriptor(moment, fitness_version=FITNESS_V1):
    c = components(moment, fitness_version)
    return (
        round(c["articulation"], 6),
        round(c["motion"], 6),
        round(c["jerk"], 6),
        round(c["glow"], 6),
        round(c["spike"], 6),
        round(c["variance"], 6),
    )


def archetype(moment, fitness_version=FITNESS_V1):
    c = components(moment, fitness_version)
    if c["motion"] < 0.18:
        return "still"
    if c["motion"] >= 0.35 and c["jerk"] < 0.12:
        return "glide"
    if c["glow"] >= 0.65 and c["variance"] >= 0.20:
        return "pulse"
    if c["articulation"] >= 0.65:
        return "sculpted"
    return "frenzy"


def niche(moment, fitness_version=FITNESS_V1):
    return f"{moment['b']}:{archetype(moment, fitness_version)}"


def distance(left, right, fitness_version=FITNESS_V1):
    a, b = descriptor(left, fitness_version), descriptor(right, fitness_version)
    return round(math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))) / math.sqrt(len(a)), 6)


def archive(moments, fitness_version=FITNESS_V1):
    elites = {}
    for moment in moments:
        cell = niche(moment, fitness_version)
        current = elites.get(cell)
        candidate_key = (strength(moment, fitness_version), moment_id(moment))
        current_key = None if current is None else (strength(current, fitness_version), moment_id(current))
        if current is None or candidate_key > current_key:
            elites[cell] = moment
    return dict(sorted(elites.items()))


def novelty(candidate, moments, fitness_version=FITNESS_V1):
    others = [moment for moment in moments if moment_id(moment) != moment_id(candidate)]
    return min((distance(candidate, moment, fitness_version) for moment in others), default=1.0)


def admission(parent, candidate, active, bar, fitness_version=FITNESS_V1):
    score = strength(candidate, fitness_version)
    cell = niche(candidate, fitness_version)
    parent_cell = niche(parent, fitness_version)
    elites = archive(active, fitness_version)
    near = novelty(candidate, active, fitness_version)
    base = {
        "niche": cell,
        "parent_niche": parent_cell,
        "novelty": near,
        "quality_floor": QUALITY_FLOOR,
        "bar": round(bar, 4),
    }
    if score < QUALITY_FLOOR:
        return {**base, "accepted": False, "reason": "below_quality_floor", "retain_parent": True}
    if near < MIN_NOVELTY:
        return {**base, "accepted": False, "reason": "descriptor_near_duplicate", "retain_parent": True}
    if cell != parent_cell:
        if cell in elites:
            return {**base, "accepted": False, "reason": "occupied_cross_niche", "retain_parent": True}
        return {**base, "accepted": True, "reason": "filled_empty_niche", "retain_parent": True}
    if moment_id(elites.get(cell)) != moment_id(parent):
        return {**base, "accepted": False, "reason": "parent_is_not_niche_elite", "retain_parent": True}
    if score < bar:
        return {**base, "accepted": False, "reason": "did_not_clear_niche_bar", "retain_parent": True}
    return {**base, "accepted": True, "reason": "replaced_niche_elite", "retain_parent": False}


def archive_document(moments, fitness_version=FITNESS_V1):
    elites = archive(moments, fitness_version)
    return {
        "fitness": fitness_version,
        "quality_floor": QUALITY_FLOOR,
        "min_novelty": MIN_NOVELTY,
        "occupied": len(elites),
        "elites": {
            cell: {
                "id": moment_id(moment),
                "strength": strength(moment, fitness_version),
                "descriptor": descriptor(moment, fitness_version),
            }
            for cell, moment in elites.items()
        },
    }
