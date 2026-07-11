import random
import json
import os
import tempfile
import unittest

from harness.diversity import admission, archive, descriptor, niche
from harness.moment import improve, mint
from harness.strength import strength
from harness.validation import moment_id
from harness.store import accept_jump, load_state, save_state


class DiversityTests(unittest.TestCase):
    def test_archive_is_input_order_invariant(self):
        moments = [mint(seed=i, n=2 + i % 6, title=f"M{i}") for i in range(20)]
        expected = {cell: moment_id(moment) for cell, moment in archive(moments).items()}
        random.Random(9).shuffle(moments)
        actual = {cell: moment_id(moment) for cell, moment in archive(moments).items()}
        self.assertEqual(actual, expected)

    def test_descriptor_and_niche_are_deterministic(self):
        moment = mint(seed=4, n=5)
        self.assertEqual(descriptor(moment), descriptor(moment))
        self.assertEqual(niche(moment), niche(moment))

    def test_cross_niche_admission_retains_parent(self):
        parent = mint(seed=1, n=2, title="Parent", biome="forest")
        child = improve(parent, boost=8, seed=8)
        decision = admission(parent, child, [parent], strength(child))
        if niche(parent) != niche(child):
            self.assertTrue(decision["accepted"])
            self.assertTrue(decision["retain_parent"])
            self.assertEqual(decision["reason"], "filled_empty_niche")
        else:
            self.assertEqual(decision["reason"], "replaced_niche_elite")

    def test_descriptor_near_clone_is_rejected(self):
        parent = mint(seed=3, n=4, title="Parent")
        clone = dict(parent)
        clone["t"] = "Parent clone"
        decision = admission(parent, clone, [parent], strength(parent) + 0.05)
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["reason"], "descriptor_near_duplicate")

    def test_empty_niche_receipt_keeps_both_lineages_active(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            parent = mint(seed=1, n=2, title="Parent", biome="forest")
            child = improve(parent, boost=8, seed=8)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"moments": [parent]}, handle)
            state = load_state(path)
            accept_jump(
                state,
                parent,
                child,
                strength(child),
                provenance={"quality_diversity": {"reason": "filled_empty_niche"}},
                retain_parent=True,
                created_at="test",
            )
            save_state(state)
            active = {moment_id(moment) for moment in load_state(path).active_moments}
            self.assertEqual(active, {moment_id(parent), moment_id(child)})


if __name__ == "__main__":
    unittest.main()
