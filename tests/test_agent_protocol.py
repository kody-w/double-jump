import json
import unittest

from agents.double_jump_agent import DoubleJumpAgent
from harness.loop import load_warehouse
from harness.moment import encode_token, improve
from harness.strength import strength


class AgentProtocolTests(unittest.TestCase):
    def setUp(self):
        self.agent = DoubleJumpAgent()
        self.moments = load_warehouse()

    def test_explicit_jump_improves_the_supplied_target(self):
        target = max(self.moments, key=strength)
        result = json.loads(self.agent.perform(action="jump", token=encode_token(target)))
        self.assertEqual(result["target"]["title"], target["t"])
        self.assertEqual(result["improvement"]["from"], strength(target))

    def test_challenge_and_propose_use_the_active_weakest(self):
        challenge = json.loads(self.agent.perform(action="challenge"))
        target = challenge["target"]
        parent = min(self.moments, key=strength)
        self.assertEqual(target["title"], parent["t"])
        child = improve(parent, boost=8, seed=8)
        result = json.loads(self.agent.perform(
            action="propose",
            target_token=target["token"],
            token=encode_token(child),
        ))
        self.assertTrue(result["cleared"])
        self.assertEqual(result["status"], "accepted")

    def test_default_policy_blocks_publication(self):
        result = json.loads(self.agent.perform(
            action="submit",
            token=encode_token(self.moments[0]),
        ))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "side_effect_denied")


if __name__ == "__main__":
    unittest.main()
