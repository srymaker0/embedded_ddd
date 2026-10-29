import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embedded_linux.inspect import inspect_profile
from support import LocalShell


class InspectTests(unittest.TestCase):
    def setUp(self):
        self.profile = {"version": 1, "name": "fixture",
                        "connection": {"type": "ssh", "host": "fixture"}}

    def inspect(self, purpose, **kwargs):
        which = shutil.which
        # This fixture executes a local shell; SSH availability is tested separately.
        with patch("embedded_linux.inspect.shutil.which",
                   side_effect=lambda name: "/fixture/ssh" if name == "ssh" else which(name)):
            return inspect_profile(self.profile, purpose, connector=lambda _: LocalShell(), **kwargs)

    def test_missing_host_dependency_fails_without_connecting(self):
        with patch("embedded_linux.inspect.shutil.which", return_value=None), \
                patch("embedded_linux.inspect.connect") as unused:
            report = inspect_profile(self.profile, connector=unused)
        self.assertFalse(report["ready"])
        unused.assert_not_called()

    def test_local_check_never_connects_or_claims_target_ready(self):
        with patch("embedded_linux.inspect.shutil.which", return_value="/usr/bin/ssh"), \
                patch("embedded_linux.inspect.connect") as unused:
            report = inspect_profile(self.profile, local=True, connector=unused)
        unused.assert_not_called()
        self.assertTrue(report["checks_passed"])
        self.assertIsNone(report["ready"])

    def test_missing_serial_does_not_hide_available_application_log(self):
        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "app.log"
            application.write_text("fixture: responsive\n")
            self.profile["logs"] = [
                {"name": "serial", "kind": "local", "path": directory + "/absent"},
                {"name": "application", "kind": "remote", "path": str(application)}]
            # No GDB or deploy configuration is needed to collect logs.
            report = self.inspect("collect")
            self.assertTrue(report["ready"], report)
            sources = {c["name"]: c["status"] for c in report["checks"]}
            self.assertEqual(sources["log:serial"], "warning")
            self.assertEqual(sources["log:application"], "passed")
            application.unlink()
            self.assertFalse(self.inspect("collect")["ready"])

    def test_inspection_does_not_execute_installer_or_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "unexpected"
            self.profile["deploy"] = {"cwd": directory, "argv": ["touch", str(marker)],
                                      "verify_command": "touch " + str(marker)}
            self.profile["logs"] = [{"name": "app", "kind": "local", "path": "/dev/null"}]
            report = self.inspect("deploy", local=True)
            self.assertTrue(report["checks_passed"], report)
            self.assertFalse(marker.exists())

    def test_missing_gdb_and_wrong_transfer_transport_are_not_ready(self):
        self.assertFalse(self.inspect("gdb-snapshot", local=True)["checks_passed"])
        self.profile["connection"] = {"type": "telnet", "host": "fixture"}
        self.profile["transfer"] = {"method": "scp"}
        self.assertFalse(self.inspect("put", local=True)["checks_passed"])

    def test_identity_mismatch_is_a_failure(self):
        self.profile["identity"] = {"command": "printf actual", "contains": "expected"}
        self.assertFalse(self.inspect("connect")["ready"])

    def test_successful_non_debugger_command_is_not_gdb_readiness(self):
        self.profile["gdb"] = {"native": "/bin/true"}
        self.assertFalse(self.inspect("gdb-snapshot")["ready"])
