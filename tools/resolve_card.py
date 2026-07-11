#!/usr/bin/env python3
"""
resolve_card.py — resolve a holocard champion into an ERC-721 / OpenSea-compatible token URI.

Mirrors the rapp-hologram resolve.js Gateway (SPEC §11¾): one standard metadata document any marketplace,
wallet, or crawler can fetch to render + verify + trade the Moment. The twist that makes it serverless:
`animation_url` is the **live walkable hologram** itself (`?m=<token>`), so the actual creature renders
*inside* the marketplace card. `image` is the self-contained SVG poster as a data URI. No server, no host —
a static JSON on the CDN, the hologram one URL away.

Usage:  python3 tools/resolve_card.py            # resolve the champion (strongest holocard)
        python3 tools/resolve_card.py --all      # materialize every active holocard
"""
import argparse
import base64
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "cards.json")
SPEC = "https://github.com/kody-w/rapp-moment/blob/main/SPEC.md"
COMMONS_DIMENSION = "rappid:dimension:0c0ba7d21766be26e61700893fd94"   # the genesis dimension


def _rappid_of(token):
    return "rappid:moment:" + hashlib.sha256(("moment:" + token).encode()).hexdigest()


def resolve(card):
    h = card["holo"]
    token = h["token"]
    play = h["play_url"]
    svg_b64 = base64.b64encode(card["avatar_svg"].encode("utf-8")).decode("ascii")
    s = card.get("stats", {})
    attrs = [
        {"trait_type": "Species", "value": card.get("morphology", {}).get("species_name")},
        {"trait_type": "Body plan", "value": card.get("morphology", {}).get("body_plan")},
        {"trait_type": "Locomotion", "value": card.get("morphology", {}).get("locomotion")},
        {"trait_type": "Biome", "value": h.get("biome")},
        {"trait_type": "Keyframes", "value": h.get("keyframes")},
        {"trait_type": "Strength", "value": h.get("strength")},
        {"trait_type": "Rarity", "value": card.get("rarity_label")},
        {"trait_type": "Author (twin)", "value": h.get("author")},
        {"trait_type": "Signed", "value": False},
        {"trait_type": "ATK · motion", "value": s.get("atk")},
        {"trait_type": "DEF · vitality", "value": s.get("def")},
        {"trait_type": "SPD · spikes", "value": s.get("spd")},
        {"trait_type": "INT · articulation", "value": s.get("int")},
    ]
    return {
        "@context": SPEC,
        "@type": "rappid:moment",
        "$schema": "erc721-metadata-compatible",
        # ---- standard NFT / marketplace metadata ----
        "name": card["name"],
        "description": (f"{card.get('flavor_text','')} A living holographic Moment — 100 frames, one "
                        f"heartbeat each. The card's art IS the walkable creature; it plays serverlessly "
                        f"from a CDN. Strength {h.get('strength')}. {play}"),
        "image": "data:image/svg+xml;base64," + svg_b64,
        "animation_url": play,         # marketplaces embed this → the ACTUAL walkable hologram renders in-place
        "external_url": play,
        "attributes": attrs,
        # ---- RAPP Eternity extensions ----
        "rappid": _rappid_of(token),
        "token": token,
        "born": None,
        "owner": h.get("author"),
        "sig_suite": "ecdsa-p256",
        "chain": {"repo": "kody-w/double-jump", "kind": "git-blockchain",
                  "validator": "https://github.com/kody-w/double-jump/commits/main/warehouse/moments.json"},
        "dimension": COMMONS_DIMENSION,
        "spec": SPEC,
        "sources": [],
    }


def _path_for(card):
    slug = card["id"].split("/")[-1]
    return os.path.join(ROOT, "resolve", slug + ".json")


def _stable_write(path, document, check=False):
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    changed = text != old
    if changed and not check:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="card id; default = the champion (strongest)")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--all", action="store_true", help="materialize metadata for every active card")
    ap.add_argument("--check", action="store_true", help="exit nonzero when generated metadata is stale")
    a = ap.parse_args()
    cards = list(json.load(open(CARDS))["cards"].values())
    if a.all:
        changed = []
        for item in cards:
            path = _path_for(item)
            if _stable_write(path, resolve(item), check=a.check):
                changed.append(os.path.relpath(path, ROOT))
        print(json.dumps({"resolved": len(cards), "changed": changed}, indent=2))
        return 1 if a.check and changed else 0
    if a.id:
        card = next((c for c in cards if c["id"] == a.id), None)
        if not card:
            print(json.dumps({"error": f"no card {a.id}"})); return 1
    else:
        card = max(cards, key=lambda c: c["holo"]["strength"])
    doc = resolve(card)
    slug = card["id"].split("/")[-1]
    if not a.no_write:
        _stable_write(_path_for(card), doc, check=a.check)
    iframe = (f'<iframe src="{doc["animation_url"]}" width="480" height="480" loading="lazy" '
              f'style="border:0;border-radius:16px" title="{card["name"]}"></iframe>')
    print(json.dumps({
        "champion": card["name"], "rarity": card.get("rarity_label"),
        "strength": card["holo"]["strength"],
        "token_uri": f"https://raw.githubusercontent.com/kody-w/double-jump/main/resolve/{slug}.json",
        "animation_url": doc["animation_url"],
        "rappid": doc["rappid"],
        "embed": iframe,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
