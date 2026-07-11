import json
import unittest

from harness.moment import decode_token, encode_token, mint
from harness.validation import MomentValidationError, moment_id, validate_moment


class ValidationTests(unittest.TestCase):
    def test_round_trip_and_identity_ignore_key_order(self):
        moment = mint(seed=7, n=4)
        self.assertEqual(decode_token(encode_token(moment)), moment)
        reordered = {key: moment[key] for key in reversed(moment)}
        self.assertEqual(moment_id(moment), moment_id(reordered))

    def test_rejects_non_finite_and_bad_timeline(self):
        moment = mint(seed=3)
        moment["k"][0]["g"] = float("nan")
        with self.assertRaises(MomentValidationError):
            validate_moment(moment)
        moment = mint(seed=3)
        moment["k"][1]["at"] = 0
        with self.assertRaises(MomentValidationError):
            validate_moment(moment)

    def test_rejects_duplicate_json_keys(self):
        raw = '{"v":1,"v":1,"t":"x","a":"@x","b":"void","k":[]}'
        import base64
        token = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        with self.assertRaisesRegex(MomentValidationError, "duplicate JSON key"):
            decode_token(token)


if __name__ == "__main__":
    unittest.main()
