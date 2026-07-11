import json
import shutil
import subprocess
import unittest

from harness.moment import mint
from harness.strength import FITNESS_V1, FITNESS_V2, components, strength


@unittest.skipUnless(shutil.which("node"), "Node.js is required for browser parity")
class FitnessParityTests(unittest.TestCase):
    def test_python_and_browser_scores_match(self):
        moments = [mint(seed=i, n=2 + i % 5) for i in range(12)]
        script = (
            "const f=require('./assets/fitness.js');"
            "const ms=JSON.parse(process.argv[1]);"
            "process.stdout.write(JSON.stringify(ms.map(m=>({"
            "v1:{s:f.strength(m),c:f.components(m)},"
            "v2:{s:f.strength(m,'v2'),c:f.componentsV2(m)}}))));"
        )
        output = subprocess.check_output(
            ["node", "-e", script, json.dumps(moments, ensure_ascii=False)],
            text=True,
        )
        browser = json.loads(output)
        for moment, result in zip(moments, browser):
            for label, version in (("v1", FITNESS_V1), ("v2", FITNESS_V2)):
                self.assertEqual(result[label]["s"], strength(moment, version))
                expected = components(moment, version)
                for key in expected:
                    self.assertAlmostEqual(result[label]["c"][key], expected[key], places=10)


if __name__ == "__main__":
    unittest.main()
