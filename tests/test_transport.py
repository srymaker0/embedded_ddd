import os
import pty
import subprocess
import tempfile
import tty
import unittest
from pathlib import Path
from unittest.mock import patch

import pexpect

from embedded_linux.profile import ToolError, password_from_file
from embedded_linux.transport import CommandError, ConnectionLost, Console


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        child = pexpect.spawn("/bin/sh", ["-i"], encoding="utf-8", echo=True)
        self.session = Console({"type": "telnet"}, child=child)

    def tearDown(self):
        self.session.close()

    def test_echo_exit_and_following_command(self):
        self.assertEqual(self.session.execute("printf 'first\\n'; exit 7", check=False), (7, "first\n"))
        self.assertEqual(self.session.execute("printf 'second\\n'"), (0, "second\n"))

    def test_quotes_and_multiline_command(self):
        self.assertEqual(self.session.execute("printf '%s\\n' \"a'b\"\nprintf '%s' end"),
                         (0, "a'b\nend"))

    def test_nonzero_exit_preserves_output(self):
        with self.assertRaises(CommandError) as failure:
            self.session.execute("printf broken; exit 4")
        self.assertEqual(failure.exception.returncode, 4)
        self.assertEqual(failure.exception.output, "broken")

    def test_timeout_invalidates_session_without_replaying(self):
        with self.assertRaises(ConnectionLost):
            self.session.execute("sleep 2", timeout=0.05)
        with self.assertRaises(ConnectionLost):
            self.session.execute("printf should-not-run")

    def test_disconnect_does_not_succeed(self):
        self.session.child.terminate(force=True)
        with self.assertRaises(ConnectionLost):
            self.session.execute("printf unreachable", timeout=0.1)

    def test_missing_telnet_client_has_an_actionable_connection_error(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"PATH": directory}):
            with self.assertRaisesRegex(ConnectionLost, "telnet"):
                Console({"type": "telnet", "host": "127.0.0.1"})


class SerialTests(unittest.TestCase):
    def test_real_pseudoterminal_shell_and_close(self):
        for shell in ("/bin/sh", "/bin/bash", "/bin/dash"):
            if not Path(shell).is_file():
                continue
            with self.subTest(shell=shell):
                master, slave = pty.openpty()
                # Prevent startup output from echoing back into the fixture shell.
                tty.setraw(slave)
                # The master end is a serial peer, not a controlling terminal.
                # Disable job control: Dash otherwise loops waiting to be foreground.
                process = subprocess.Popen([shell, "-i", "+m"], stdin=master, stdout=master,
                                           stderr=master, start_new_session=True)
                session = None
                try:
                    session = Console({"type": "serial", "device": os.ttyname(slave), "timeout": 3})
                    self.assertEqual(session.execute("printf serial-ok"), (0, "serial-ok"))
                    session.close()
                    self.assertFalse(session.serial.is_open)
                finally:
                    if session:
                        session.close()
                    process.terminate()
                    try:
                        process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        process.kill()  # Interactive shells may ignore TERM; this PID is our fixture.
                        process.wait(timeout=3)
                    os.close(master)
                    os.close(slave)


class CredentialTests(unittest.TestCase):
    def test_credential_permissions_are_checked_without_disclosing_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            path.write_text("fixture-secret\n")
            path.chmod(0o644)
            with self.assertRaises(ToolError) as failure:
                password_from_file(path)
            self.assertNotIn("fixture-secret", str(failure.exception))
            path.chmod(0o600)
            self.assertEqual(password_from_file(path), "fixture-secret")
