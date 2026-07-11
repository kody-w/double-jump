import json
import shutil
import subprocess
import unittest

from tools.mint_cards import SPECIES, build_documents


class SpeciesDiversityTests(unittest.TestCase):
    def test_active_population_has_unique_body_plans(self):
        deck, _ = build_documents()
        cards = list(deck["cards"].values())
        self.assertEqual(len(cards), len(SPECIES))
        body_plans = [card["morphology"]["body_plan"] for card in cards]
        species_ids = [card["morphology"]["species_id"] for card in cards]
        species_names = [card["morphology"]["species_name"] for card in cards]
        self.assertEqual(len(body_plans), len(set(body_plans)))
        self.assertEqual(len(species_ids), len(set(species_ids)))
        self.assertEqual(len(species_names), len(set(species_names)))
        for card in cards:
            morphology = card["morphology"]
            self.assertIn(morphology["species_name"], card["avatar_svg"])
            self.assertTrue(morphology["locomotion"])
            self.assertTrue(morphology["surface"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for renderer metadata")
    def test_browser_renderer_declares_all_body_plans(self):
        output = subprocess.check_output(
            ["node", "-e", "process.stdout.write(JSON.stringify(require('./assets/species.js').plans))"],
            text=True,
        )
        self.assertEqual(json.loads(output), [row[0] for row in SPECIES])


if __name__ == "__main__":
    unittest.main()
