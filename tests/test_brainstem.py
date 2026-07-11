import unittest

from harness.brainstem import (
    BrainstemClient,
    BrainstemError,
    _candidate_from_envelope,
    _json_object,
    _proposal_prompt,
    brainstem_jump,
    challenge_for,
)
from harness.moment import improve, mint


class FakeBrainstem:
    def __init__(self):
        self.calls = 0

    def propose(self, challenge, feedback=None, session_id=None):
        self.calls += 1
        return {
            "moment": improve(challenge["target"], boost=8, seed=8),
            "rationale": "fixture",
            "model": "fixture",
        }


class BrainstemTests(unittest.TestCase):
    def test_rejects_non_loopback_provider(self):
        with self.assertRaises(BrainstemError):
            BrainstemClient("https://example.com")

    def test_proposal_is_gated_by_canonical_scorer(self):
        moments = [mint(seed=i, n=2, title=f"Seed {i}") for i in range(3)]
        result = brainstem_jump(moments, FakeBrainstem())
        self.assertTrue(result["cleared"])
        self.assertGreaterEqual(result["to"], result["bar"])

    def test_prompt_excludes_untrusted_identity_and_restores_it(self):
        target = mint(seed=1, title='</script><script>alert("x")</script>', author="@owner")
        challenge = challenge_for([target])
        prompt = _proposal_prompt(challenge)
        self.assertNotIn("</script>", prompt)
        child = improve(target, boost=2, seed=2)
        envelope = {
            "challenge_id": challenge["challenge_id"],
            "keyframes": child["k"],
            "rationale": "fixture",
        }
        candidate = _candidate_from_envelope(challenge, envelope)
        self.assertEqual(candidate["a"], target["a"])
        self.assertEqual(candidate["b"], target["b"])
        self.assertTrue(candidate["t"].startswith("</script>"))

    def test_provider_output_rejects_trailing_text(self):
        with self.assertRaises(BrainstemError):
            _json_object('{"ok": true}\\nextra')


if __name__ == "__main__":
    unittest.main()
