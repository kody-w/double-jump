import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from harness.moment import encode_token, mint
from harness.store import load_state
from tools import ingest


class IngestTests(unittest.TestCase):
    def _run(self, path, body):
        output = io.StringIO()
        with mock.patch.object(ingest, "WAREHOUSE", path), \
                mock.patch.dict(os.environ, {"ISSUE_BODY": body}, clear=False), \
                contextlib.redirect_stdout(output):
            code = ingest.main()
        return code, json.loads(output.getvalue())

    def test_create_is_validated_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            token = encode_token(mint(seed=1, title="Safe"))
            body = f"### op\ncreate\n\n### token\n```\n{token}\n```"
            code, result = self._run(path, body)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "submitted")
            code, result = self._run(path, body)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "duplicate")
            state = load_state(path)
            self.assertEqual(len(state.moments), 1)
            self.assertEqual(len(state.active_moments), 0)

    def test_public_delete_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "moments.json")
            token = encode_token(mint(seed=2, title="Keep"))
            self._run(path, f"### op\ncreate\n\n### token\n{token}")
            before = Path(path).read_text(encoding="utf-8")
            code, result = self._run(path, f"### op\ndelete\n\n### token\n{token}")
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "error")
            self.assertEqual(Path(path).read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
