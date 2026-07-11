#!/usr/bin/env python3
"""
mint_cards.py — turn the twin's holograms into actual RAPPcards.

The warehouse holds living Moments (holograms). The cards network (RAR / RAPPcards / binders like
red-binder) holds `rappcards/1.0` card records. This tool bridges them: every Moment becomes a **holocard**
— a collectible card whose **art is the live hologram** (its `?m=<token>` player URL) and whose stats are
derived from the Moment's own strength components. Output is a self-contained binder deck (`cards.json`)
plus the federation index (`seed-index.json`), exactly the shape a third-party binder uses.

Deterministic, dependency-free. Run from the repo root: `python3 tools/mint_cards.py`.
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.moment import encode_token            # noqa: E402
from harness.store import load_state                # noqa: E402
from harness.strength import strength, components  # noqa: E402
from harness.validation import moment_id            # noqa: E402

WAREHOUSE = os.path.join(ROOT, "warehouse", "moments.json")
PLAYER = "https://kody-w.github.io/rapp-hologram/"
RAW = "https://raw.githubusercontent.com/kody-w/double-jump/main"
HOMEPAGE = "https://kody-w.github.io/double-jump/pokedex.html"
BIOME_HEX = {"savanna": "#6fae4a", "canyon": "#d8a86a", "forest": "#35e0c0",
             "volcanic": "#ff5a3c", "void": "#6f8cff"}
BIOME_BG = {"savanna": "#1c2a14", "canyon": "#2a1c0e", "forest": "#0a1f1c",
            "volcanic": "#2a0e0e", "void": "#0a0a16"}
SPECIES = [
    ("orbital", "Orbital Grazer", "levitation", 0, "rings", "radial", "glass"),
    ("beetle", "Prism Beetle", "hexapod", 6, "shell-wings", "bilateral", "carapace"),
    ("manta", "Sky Manta", "gliding", 2, "ribbon-tail", "bilateral", "silk"),
    ("serpent", "Segment Serpent", "slithering", 0, "crest", "linear", "scales"),
    ("tripod", "Crystal Tripod", "tripod", 3, "crown", "triangular", "crystal"),
    ("jelly", "Lantern Jelly", "floating", 8, "tendrils", "radial", "translucent"),
    ("flower", "Bloom Walker", "root-walking", 5, "petals", "radial", "botanical"),
    ("walker", "Tower Walker", "quadruped", 4, "banner-head", "bilateral", "stone"),
    ("crystal", "Shard Swarm", "orbiting", 7, "satellites", "asymmetric", "faceted"),
    ("ring", "Halo Engine", "rolling", 4, "orbitals", "radial", "metallic"),
]


def _blake64(s):
    return str(int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big"))


def _slug(t):
    out = "".join(c.lower() if c.isalnum() else "-" for c in (t or "moment"))
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:48] or "moment"


def _rarity(s):
    return (("legendary", "Legendary") if s >= 0.6 else
            ("rare", "Rare") if s >= 0.45 else
            ("uncommon", "Uncommon") if s >= 0.3 else
            ("common", "Common"))


def morphology_of(m, index):
    body, name, locomotion, limbs, ornament, symmetry, surface = SPECIES[index % len(SPECIES)]
    hue = int((m.get("k") or [{}])[0].get("h", 200)) % 360
    digest = moment_id(m).split(":", 1)[1]
    return {
        "species_id": f"{body}-{digest[:8]}",
        "species_name": name,
        "body_plan": body,
        "locomotion": locomotion,
        "limbs": limbs,
        "ornament": ornament,
        "symmetry": symmetry,
        "surface": surface,
        "primary_hue": hue,
        "secondary_hue": (hue + 67 + index * 19) % 360,
        "scale": round(0.82 + (int(digest[8:10], 16) / 255) * 0.36, 3),
    }


def _avatar_svg(m, c, morphology):
    """A deterministic poster whose silhouette matches the organism's unique species."""
    biome = m.get("b", "void")
    bg = BIOME_BG.get(biome, "#0a0a16")
    hue = morphology["primary_hue"]
    second = morphology["secondary_hue"]
    n = len(m.get("k", []))
    plan = morphology["body_plan"]
    silhouettes = {
        "orbital": '<circle cx="60" cy="57" r="25"/><ellipse cx="60" cy="57" rx="39" ry="12" fill="none" stroke-width="5"/>',
        "beetle": '<ellipse cx="60" cy="57" rx="27" ry="33"/><path d="M60 25v65M35 43 18 30M35 57 14 57M35 72 18 86M85 43l17-13M85 57l21 0M85 72l17 14" fill="none" stroke-width="5"/>',
        "manta": '<path d="M15 52Q38 20 60 48Q82 20 105 52Q82 75 60 63Q38 75 15 52Z"/><path d="M60 62q8 25 2 43" fill="none" stroke-width="5"/>',
        "serpent": '<path d="M16 72Q35 25 55 66T104 45" fill="none" stroke-width="17" stroke-linecap="round"/><circle cx="103" cy="45" r="13"/>',
        "tripod": '<path d="M60 20 87 61 60 78 33 61Z"/><path d="M60 74v31M43 68 25 98M77 68l18 30" fill="none" stroke-width="6"/>',
        "jelly": '<path d="M28 59a32 32 0 0 1 64 0Z"/><path d="M36 58q-8 24 2 45M50 58q-5 28 2 48M64 58q6 24-1 45M78 58q9 25 1 44" fill="none" stroke-width="5"/>',
        "flower": '<circle cx="60" cy="57" r="13"/><g><ellipse cx="60" cy="28" rx="12" ry="22"/><ellipse cx="60" cy="86" rx="12" ry="22"/><ellipse cx="31" cy="57" rx="22" ry="12"/><ellipse cx="89" cy="57" rx="22" ry="12"/></g>',
        "walker": '<rect x="39" y="24" width="42" height="50" rx="8"/><rect x="48" y="12" width="36" height="24" rx="7"/><path d="M45 72 34 105M55 73l-2 33M68 73l3 33M78 72l12 33" fill="none" stroke-width="7"/>',
        "crystal": '<path d="M60 16 87 48 75 91 38 99 20 57Z"/><path d="M15 26 25 35 18 46ZM92 19 106 31 94 42ZM93 79 108 90 93 102Z"/>',
        "ring": '<circle cx="60" cy="57" r="29" fill="none" stroke-width="14"/><circle cx="60" cy="57" r="8"/><circle cx="19" cy="39" r="7"/><circle cx="101" cy="75" r="7"/>',
    }
    glow = c["glow"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">'
            f'<defs><radialGradient id="g" cx="50%" cy="38%">'
            f'<stop offset="0%" stop-color="hsl({hue} 80% {40 + int(glow*30)}%)"/>'
            f'<stop offset="100%" stop-color="{bg}"/></radialGradient></defs>'
            f'<rect width="120" height="120" fill="url(#g)"/>'
            f'<g fill="hsl({hue} 75% 58%)" stroke="hsl({second} 85% 68%)">{silhouettes[plan]}</g>'
            f'<text x="60" y="112" font-size="9" text-anchor="middle" fill="#fff" opacity="0.7" '
            f'font-family="monospace">{morphology["species_name"]} · {n}f</text></svg>')


def card_of(m, morphology=None):
    s = strength(m)
    c = components(m)
    morphology = morphology or morphology_of(m, 0)
    legacy_id = f"@double-jump/{_slug(m.get('t'))}"
    cid = f"@double-jump/{moment_id(m).split(':', 1)[1][:24]}"
    rt, rl = _rarity(s)
    token = encode_token(m)
    champ = "won the triple jump" in (m.get("t") or "")
    dj = "double-jumped" in (m.get("t") or "")
    abilities = [{"name": "Double Jump", "cost": 1, "damage": round(c["motion"] * 40),
                  "text": "Leapfrog the weakest. Gain strength equal to your motion energy."}]
    if champ:
        abilities.append({"name": "Triple Jump", "cost": 2, "damage": round(s * 60),
                          "text": "Three hops, one crown. This organism won its tournament."})
    return cid, {
        "id": cid,
        "aliases": [legacy_id],
        "name": (m.get("t") or "Moment").split(" · ")[0],
        "title": m.get("t"),
        "seed": _blake64(cid),
        "hp": 40 + round(s * 60),
        "stats": {"atk": round(c["motion"] * 100), "def": round(c["vitality"] * 100),
                  "spd": round(c["spike"] * 100), "int": round(c["articulation"] * 100)},
        "agent_types": ["HOLO", (m.get("b") or "void").upper()],
        "weakness": "STILLNESS",
        "resistance": "MOTION",
        "rarity_tier": rt,
        "rarity_label": rl,
        "abilities": abilities,
        "retreat_cost": 1,
        "evolution": {"stage": 2 if dj or champ else 1, "label": "Evolved" if dj or champ else "Basic",
                      "icon": "👑" if champ else "✦" if dj else "◷"},
        "flavor_text": f"A living {m.get('b','void')} hologram — {len(m.get('k',[]))} heartbeats, strength {s}.",
        "morphology": morphology,
        "avatar_svg": _avatar_svg(m, c, morphology),
        "holo": {                                   # the card's art IS this live, walkable hologram
            "token": token,
            "play_url": PLAYER + "?m=" + token,
            "animation_url": PLAYER + "?m=" + token,
            "strength": s,
            "biome": m.get("b"),
            "keyframes": len(m.get("k", [])),
            "author": m.get("a"),
        },
        "meta": {"version": "1.0.0", "category": "double-jump", "author": m.get("a", "@double-jump"),
                 "quality_tier": "experimental", "license": "PolyForm-Noncommercial-1.0.0",
                 "description": m.get("t")},
    }


def build_documents():
    state = load_state(WAREHOUSE)
    moments = sorted(state.active_moments, key=moment_id)
    cards = {}
    seeds = {}
    for index, m in enumerate(moments):
        cid, card = card_of(m, morphology_of(m, index))
        cards[cid] = card
        seeds[card["seed"]] = {"id": cid, "name": card["name"], "rarity_tier": card["rarity_tier"],
                               "url": RAW + "/cards.json", "url_is_bundle": True, "bundle_key": cid,
                               "binder": "double-jump", "upstream": "double-jump"}
    deck = {"_meta": {"schema": "rappcards/1.0", "registry": "double-jump", "homepage": HOMEPAGE,
                      "total": len(cards),
                      "frontier_revision": state.revision,
                      "description": "Double Jump — holocards minted from living holograms. Each card's art is the live walkable Moment."},
            "cards": cards, "agents": {}}
    index = {"schema": "rappcards-seed-index/1.0", "binder": "double-jump", "homepage": HOMEPAGE,
             "cards_url": RAW + "/cards.json", "count": len(cards), "seeds": seeds}

    return deck, index


def stable_write(path, obj, check=False):
    new = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    changed = new != old
    if changed and not check:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(new)
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    deck, index = build_documents()
    cards = deck["cards"]
    a = stable_write(os.path.join(ROOT, "cards.json"), deck, args.check)
    b = stable_write(os.path.join(ROOT, "seed-index.json"), index, args.check)
    print(json.dumps({"minted": len(cards), "cards_changed": a, "index_changed": b,
                      "rarities": {r: sum(1 for c in cards.values() if c["rarity_tier"] == r)
                                   for r in ("legendary", "rare", "uncommon", "common")}}, indent=2))
    if args.check and (a or b):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
