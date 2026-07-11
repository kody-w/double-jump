import json
import os
import tempfile
import unittest
from unittest import mock

from harness.loop import run
from harness.moment import improve, mint
from harness.store import accept_jump, load_state, save_state
from harness.strength import strength
from harness.validation import moment_id


class StoreTests(unittest.TestCase):
    def test_deduplicates_and_retires_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            parent = mint(seed=1, n=2, title="Parent")
            child = improve(parent, boost=3, seed=3)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"moments": [parent, parent, child]}, handle)
            state = load_state(path)
            self.assertEqual(len(state.moments), 2)
            changed, status = accept_jump(
                state,
                parent,
                child,
                strength(child),
                created_at="test",
                allow_existing_child=True,
            )
            self.assertTrue(changed)
            self.assertEqual(status, "accepted")
            self.assertNotIn(moment_id(parent), state.active_ids)
            self.assertIn(moment_id(child), state.active_ids)
            self.assertTrue(save_state(state))
            changed, status = accept_jump(state, child, child, strength(child), created_at="test")
            self.assertFalse(changed)
            self.assertEqual(status, "duplicate")

    def test_rounds_raise_active_floor_without_duplicate_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            moments = [mint(seed=i, n=2, title=f"Seed {i}") for i in range(3)]
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"moments": moments}, handle)
            before = min(map(strength, moments))
            result = run(rounds=3, path=path)
            state = load_state(path)
            self.assertEqual(result["accepted"], 3)
            self.assertGreater(min(map(strength, state.active_moments)), before)
            ids = [moment_id(moment) for moment in state.moments]
            self.assertEqual(len(ids), len(set(ids)))

    def test_tampered_receipt_fails_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            parent = mint(seed=5, n=2, title="Parent")
            child = improve(parent, boost=4, seed=4)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"moments": [parent]}, handle)
            state = load_state(path)
            accept_jump(state, parent, child, strength(child), created_at="test")
            save_state(state)
            ledger_path = os.path.join(directory, "moments.evolution.json")
            with open(ledger_path, encoding="utf-8") as handle:
                ledger = json.load(handle)
            ledger["events"][0]["to"] += 0.1
            with open(ledger_path, "w", encoding="utf-8") as handle:
                json.dump(ledger, handle)
            with self.assertRaisesRegex(ValueError, "score does not verify"):
                load_state(path)

    def test_transaction_fault_rolls_forward_on_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            parent = mint(seed=7, n=2, title="Parent")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"moments": [parent]}, handle)
            state = load_state(path)
            child = improve(parent, boost=4, seed=4)
            accept_jump(state, parent, child, strength(child), created_at="test")
            with mock.patch.dict(os.environ, {"DOUBLE_JUMP_FAULT_AFTER_REPLACE": "1"}):
                with self.assertRaisesRegex(RuntimeError, "injected transaction fault"):
                    save_state(state)
            recovered = load_state(path)
            self.assertIn(moment_id(child), recovered.active_ids)
            self.assertFalse(os.path.exists(os.path.join(directory, "moments.transaction.json")))

    def test_stale_writer_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            parent = mint(seed=8, n=2, title="Parent")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"moments": [parent]}, handle)
            first, stale = load_state(path), load_state(path)
            child_a = improve(parent, boost=3, seed=3)
            accept_jump(first, parent, child_a, strength(child_a), created_at="first")
            save_state(first)
            child_b = improve(parent, boost=4, seed=4)
            accept_jump(stale, parent, child_b, strength(child_b), created_at="stale")
            with self.assertRaisesRegex(RuntimeError, "stale warehouse revision"):
                save_state(stale)


if __name__ == "__main__":
    unittest.main()
