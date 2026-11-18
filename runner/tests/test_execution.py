"""Set HLV_FIXTURE to upstream tests/fixtures/execution-evidence-project."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("HLV_FIXTURE"), "requires the upstream HLV sample project")
class ExecutionEvidence(unittest.TestCase):
    def test_outcome_is_bound_to_the_actual_inputs_and_process(self):
        cases = [
            ("passed", [sys.executable, "-c", "from pathlib import Path; assert '1' in Path('llm/src/value.sh').read_text()"], 0),
            ("failed", [sys.executable, "-c", "raise SystemExit(1)"], 1),
            ("skipped", None, 1),
            ("incomplete", [sys.executable, "-c", "from pathlib import Path; Path('llm/src/value.sh').write_text('echo 2')"], 1),
        ]
        for expected, command, code in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "app"
                shutil.copytree(os.environ["HLV_FIXTURE"], root)
                plan = Path(temp) / "runners.json"
                plan.write_text(json.dumps({"demo": command}))
                call = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "lekalo_hlv_run.py"),
                                      "--root", str(root), "--plan", str(plan), "--run-id", "ci-job",
                                      "--revision", "test-revision", "--hlv", os.environ.get("HLV_BIN", "hlv")],
                                      capture_output=True)
                self.assertEqual(call.returncode, code, call.stderr.decode())
                record = json.loads((root / "validation/execution-evidence.yaml").read_bytes())["runs"][0]
                self.assertEqual(record["outcome"], expected)
                self.assertTrue((root / record["artifact_ref"]).is_file())
