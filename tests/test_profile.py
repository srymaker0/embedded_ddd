import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embedded_linux.cli import main
from embedded_linux.profile import ToolError, load_profile


class ProfileTests(unittest.TestCase):
    def test_examples_are_loadable(self):
        for path in (Path(__file__).parents[1] / "examples").glob("*.json"):
            with self.subTest(path=path.name):
                self.assertTrue(load_profile(path)["name"])

    def test_invalid_connection_and_symbol_policy_fail_before_device_access(self):
        base = {"version": 1, "name": "fixture", "connection": {"type": "ssh", "host": "fixture"}}
        cases = [
            {"gdb": {"auto_solib_add": "false"}},
            {"connection": {"type": "ssh", "host": "-Fmalicious"}},
            {"connection": {"type": "ssh", "host": 123}},
            {"connection": {"type": "ssh", "host": "fixture", "user": None}},
            {"connection": {"type": "ssh", "host": "fixture", "config_file": []}},
            {"connection": {"type": "serial"}},
            {"connection": {"type": "serial", "device": 7}},
            {"connection": {"type": "telnet", "host": "fixture", "password_file": None}},
            {"connection": {"type": "ssh", "host": "fixture", "password_file": "ignored-secret"}},
            {"logs": None},
            {"probes": [{"name": "../outside", "command": "true"}]},
            {"transfer": {"method": "guess"}},
            {"identity": {}},
            {"identity": []},
            {"identity": {"command": "", "contains": "board"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            for case in cases:
                with self.subTest(case=case):
                    path.write_text(json.dumps({**base, **case}))
                    with self.assertRaises(ToolError):
                        load_profile(path)

    def test_cli_reports_invalid_configuration_without_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            profile.write_text(json.dumps({"version": 1, "name": "fixture",
                                           "connection": {"type": "ssh", "host": 123}}))
            error = io.StringIO()
            with patch("embedded_linux.cli.connect") as connect, contextlib.redirect_stderr(error):
                self.assertEqual(main(["--profile", str(profile), "inspect"]), 2)
            connect.assert_not_called()
            self.assertIn("connection.host", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())
