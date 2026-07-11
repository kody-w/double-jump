import copy
import unittest

from harness.moment import draft_improvements, mint
from harness.strength import strength
from harness.validation import moment_id, validate_moment


class EvolutionDraftTests(unittest.TestCase):
    def test_three_profiles_are_deterministic_and_do_not_mutate_parent(self):
        parent = mint(seed=9, n=2, title="Parent", author="@owner", biome="forest")
        before = copy.deepcopy(parent)
        first = draft_improvements(parent)
        second = draft_improvements(parent)
        self.assertEqual(parent, before)
        self.assertEqual(first, second)
        self.assertEqual([profile for profile, _ in first], ["motion", "articulation", "radiance"])
        self.assertEqual(len({moment_id(moment) for _, moment in first}), 3)
        for _, moment in first:
            validate_moment(moment)
            self.assertEqual(moment["a"], parent["a"])
            self.assertEqual(moment["b"], parent["b"])

    def test_at_least_one_draft_clears_a_standard_parent_margin(self):
        parent = mint(seed=4, n=2, title="Parent")
        bar = strength(parent) + 0.05
        self.assertTrue(any(strength(moment) >= bar for _, moment in draft_improvements(parent)))


if __name__ == "__main__":
    unittest.main()
