import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from embedded_linux.debug import native_snapshot
from support import LocalShell


@unittest.skipUnless(shutil.which("gdb") and shutil.which("gcc"), "requires host GDB and GCC")
class NativeGDBTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        binary = self.root / "target"
        subprocess.run(["gcc", "-g", "-O0", str(Path(__file__).parent / "fixtures/debug_target.c"),
                        "-o", str(binary)], check=True, timeout=30)
        self.process = subprocess.Popen([str(binary)], stdout=subprocess.PIPE)
        self.assertEqual(self.process.stdout.readline(), b"ready\n")
        self.profile = {"name": "disposable-host-fixture", "gdb": {"native": shutil.which("gdb")}}

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.process.stdout.close()
        self.temporary.cleanup()

    def test_real_attach_stack_detach_and_same_process_resumed(self):
        result = native_snapshot(self.profile, self.process.pid, self.root,
                                 connector=lambda _: LocalShell())
        self.assertEqual(result["result"], "snapshot_collected", result)
        self.assertTrue(result["restored"])
        self.assertEqual(result["before"]["start_ticks"], result["after"]["start_ticks"])
        self.assertIn("main", (self.root / "gdb.txt").read_text())
        self.assertIsNone(self.process.poll())

    def test_debugger_failure_is_not_reported_as_snapshot(self):
        self.profile["gdb"]["native"] = "/bin/false"
        result = native_snapshot(self.profile, self.process.pid, self.root,
                                 connector=lambda _: LocalShell())
        self.assertEqual(result["result"], "not_started")
        self.assertIn("error", result)
        self.assertIsNone(self.process.poll())

    def test_timeout_is_failure_even_if_process_is_still_healthy(self):
        fake = self.root / "slow-gdb"
        fake.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo fixture; else exec sleep 10; fi\n')
        fake.chmod(0o700)
        self.profile["gdb"]["native"] = str(fake)
        result = native_snapshot(self.profile, self.process.pid, self.root, timeout=1,
                                 connector=lambda _: LocalShell())
        self.assertEqual(result["result"], "failed", result)
        self.assertTrue(result["restored"])
