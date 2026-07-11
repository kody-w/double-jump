#!/usr/bin/env python3
"""Compare every artifact under all published fitness profiles."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.store import load_state  # noqa: E402
from harness.strength import FITNESS_V1, FITNESS_V2, strength  # noqa: E402
from harness.validation import moment_id  # noqa: E402


def main():
    state = load_state()
    rows = [{
        "id": moment_id(moment),
        "title": moment["t"],
        "v1": strength(moment, FITNESS_V1),
        "v2": strength(moment, FITNESS_V2),
    } for moment in state.moments]
    print(json.dumps({"profiles": [FITNESS_V1, FITNESS_V2], "artifacts": rows}, indent=2))


if __name__ == "__main__":
    main()
