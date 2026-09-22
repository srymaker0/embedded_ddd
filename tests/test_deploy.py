import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embedded_linux.cli import deploy
from embedded_linux.logs import Collector
from support import LocalShell


class DeploymentTests(unittest.TestCase):
    def run_deployment(self, code, timeout=3):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        serial = root / "serial.log"
        serial.write_text("before deployment\n")
        script = root / "installer.py"
        script.write_text("from pathlib import Path\nimport time\n"
                          "with Path('serial.log').open('a') as f: f.write('during deployment\\n')\n" + code)
        profile = {"name": "fixture", "connection": {"type": "ssh"},
                   "logs": [{"name": "serial", "kind": "local", "path": str(serial)}],
                   "deploy": {"argv": [sys.executable, str(script)], "cwd": str(root),
                              "verify_command": "true"}}
        args = argparse.Namespace(output=str(root / "output"), max_bytes=65536,
                                  interval=0.02, timeout=timeout, observe=0)
        def collector(profile, output, limit):
            return Collector(profile, output, limit, connector=lambda _: LocalShell())
        with patch("embedded_linux.cli.Collector", collector), contextlib.redirect_stdout(io.StringIO()):
            result = deploy(profile, args)
        output = root / "output"
        return result, json.loads((output / "deployment.json").read_text()), output, serial

    def test_observation_starts_before_installer_and_captures_incremental_output(self):
        code, result, output, _ = self.run_deployment("time.sleep(0.08)\n")
        self.assertEqual(code, 0)
        self.assertEqual(result["verification"], "passed")
        evidence = json.loads((output / "diagnostics.json").read_text())
        baseline = evidence["cycles"][0]["sources"][0]
        self.assertTrue(baseline["context_only"])
        self.assertEqual((output / baseline["file"]).read_text(), "before deployment\n")
        incremental = [s for c in evidence["cycles"][1:] for s in c["sources"] if s.get("file")]
        self.assertTrue(any("during deployment" in (output / s["file"]).read_text() and
                            not s["context_only"] for s in incremental))

    def test_installer_failure_remains_failure_with_logs(self):
        code, result, output, _ = self.run_deployment("raise SystemExit(7)\n")
        self.assertEqual(code, 2)
        self.assertEqual(result["result"], "installer_failed")
        self.assertEqual(result["returncode"], 7)
        self.assertTrue((output / "diagnostics.json").exists())

    def test_timeout_records_unknown_outcome_and_does_not_retry(self):
        code, result, _, serial = self.run_deployment("time.sleep(10)\n", timeout=0.15)
        self.assertEqual(code, 2)
        self.assertEqual(result["result"], "outcome_unknown")
        self.assertEqual(serial.read_text().count("during deployment"), 1)
