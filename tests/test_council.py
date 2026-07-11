import random
import tempfile
import unittest

from harness.council import CouncilConsensusError, STRATEGIES, consensus, run_council, write_receipt


class FakeProvider:
    def complete_json(self, prompt):
        strategy_id = next(strategy_id for strategy_id, _ in STRATEGIES if f"`{strategy_id}`" in prompt)
        return {
            "strategy_id": strategy_id,
            "proposals": [
                {
                    "feature_id": feature_id,
                    "title": title,
                    "priority": priority,
                    "scope": "M",
                    "rationale": title,
                    "files": ["harness/example.py"],
                    "acceptance": ["The behavior is covered by a deterministic test."],
                }
                for feature_id, title, priority in (
                    ("lineage-observatory", "Lineage observatory", 99),
                    ("cycle-receipts", "Cycle receipts", 97),
                    ("accessible-shell", "Accessible shell", 95),
                    (f"{strategy_id}-specialist", f"{strategy_id} specialist feature", 90),
                    (f"{strategy_id}-experiment", f"{strategy_id} experiment", 80),
                )
            ],
        }


class CouncilTests(unittest.TestCase):
    def test_exact_eight_and_deterministic_consensus(self):
        snapshot = {"digest": "sha256:fixture"}
        receipt = run_council(FakeProvider(), snapshot, created_at="test")
        self.assertEqual(len(receipt["strategies"]), 8)
        self.assertEqual(receipt["top_three"], [
            "lineage-observatory",
            "cycle-receipts",
            "accessible-shell",
        ])
        ballots = [
            {"strategy_id": item["strategy_id"], "proposals": item["proposals"]}
            for item in receipt["strategies"]
        ]
        expected = consensus(ballots)
        random.Random(4).shuffle(ballots)
        self.assertEqual(consensus(ballots), expected)

    def test_receipt_write_is_idempotent(self):
        receipt = run_council(FakeProvider(), {"digest": "sha256:fixture"}, created_at="test")
        with tempfile.TemporaryDirectory() as directory:
            first = write_receipt(directory, receipt)
            second = write_receipt(directory, receipt)
            self.assertEqual(first, second)

    def test_single_strategy_ideas_do_not_count_as_consensus(self):
        class UniqueProvider(FakeProvider):
            def complete_json(self, prompt):
                ballot = super().complete_json(prompt)
                strategy_id = ballot["strategy_id"]
                for index, proposal in enumerate(ballot["proposals"]):
                    proposal["feature_id"] = f"{strategy_id}-z{index}"
                    proposal["title"] = f"{strategy_id} q{index}"
                return ballot

        with self.assertRaisesRegex(CouncilConsensusError, "fewer than three") as raised:
            run_council(UniqueProvider(), {"digest": "sha256:fixture"}, created_at="test")
        self.assertEqual(raised.exception.receipt["status"], "insufficient_consensus")
        self.assertLess(len(raised.exception.receipt["top_three"]), 3)

    def test_completed_consensus_is_excluded(self):
        receipt = run_council(
            FakeProvider(),
            {"digest": "sha256:fixture"},
            completed_features=["lineage-observatory"],
            created_at="test",
        )
        self.assertNotIn("lineage-observatory", receipt["top_three"])
        self.assertEqual(receipt["completed_features"], ["lineage-observatory"])


if __name__ == "__main__":
    unittest.main()
