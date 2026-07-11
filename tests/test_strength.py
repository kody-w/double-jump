import unittest

from harness.moment import mint
from harness.strength import FITNESS_V1, FITNESS_V2, strength


class StrengthVersionTests(unittest.TestCase):
    def test_v1_is_frozen_and_v2_resists_keyframe_stuffing(self):
        base = {
            "v": 1,
            "t": "Still",
            "a": "@fixture",
            "b": "void",
            "k": [
                {"at": 0, "s": 0.5, "l": 0.5, "p": 0.4, "g": 0.6, "h": 120, "x": 0, "z": 0},
                {"at": 99, "s": 0.5, "l": 0.5, "p": 0.4, "g": 0.6, "h": 120, "x": 0, "z": 0},
            ],
        }
        stuffed = dict(base)
        stuffed["k"] = [
            {"at": at, "s": 0.5, "l": 0.5, "p": 0.4, "g": 0.6, "h": 120, "x": 0, "z": 0}
            for at in range(100)
        ]
        self.assertGreater(strength(stuffed, FITNESS_V1), strength(base, FITNESS_V1))
        self.assertEqual(strength(stuffed, FITNESS_V2), strength(base, FITNESS_V2))

    def test_v2_penalizes_boundary_saturation(self):
        balanced = mint(seed=14, n=6, title="Balanced")
        saturated = mint(seed=14, n=6, title="Saturated")
        for index, frame in enumerate(saturated["k"]):
            edge = 1 if index % 2 else 0
            for field in ("s", "l", "p", "g"):
                frame[field] = edge
            frame["x"] = 1 if index % 2 else -1
            frame["z"] = -frame["x"]
        self.assertLess(strength(saturated, FITNESS_V2), strength(balanced, FITNESS_V2))

    def test_unknown_version_fails_closed(self):
        with self.assertRaises(ValueError):
            strength(mint(seed=1), "future")


if __name__ == "__main__":
    unittest.main()
