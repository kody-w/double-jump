import json
import os
import tempfile
import unittest

from harness.policy import PolicyViolation, new_budget


class PolicyTests(unittest.TestCase):
    def test_limits_and_side_effects_fail_closed(self):
        budget = new_budget()
        budget.authorize_rounds(8)
        with self.assertRaisesRegex(PolicyViolation, "rounds"):
            budget.authorize_rounds(9)
        budget.consume_provider(24)
        with self.assertRaisesRegex(PolicyViolation, "provider call"):
            budget.consume_provider()
        with self.assertRaisesRegex(PolicyViolation, "direct_push"):
            budget.authorize_side_effect("direct_push", explicit=True)
        self.assertTrue(budget.authorize_side_effect("promotion_pr", explicit=True))

    def test_policy_digest_is_deterministic(self):
        first = new_budget().policy_digest
        second = new_budget().policy_digest
        self.assertEqual(first, second)

    def test_invalid_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "policy.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"schema": "wrong"}, handle)
            with self.assertRaises(PolicyViolation):
                new_budget(path)


if __name__ == "__main__":
    unittest.main()
