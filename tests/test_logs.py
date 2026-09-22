import tempfile
import unittest
from pathlib import Path

from embedded_linux.logs import Collector, LocalLog, remote_log
from support import LocalShell


class LogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "console.log"

    def tearDown(self):
        self.temporary.cleanup()

    def test_baseline_is_context_and_append_is_incremental(self):
        self.path.write_bytes(b"old\n")
        source = LocalLog(self.path)
        state, data = source.read(1024)
        self.assertTrue(state["context_only"])
        with self.path.open("ab") as stream:
            stream.write(b"new\n")
        state, data = source.read(1024)
        self.assertFalse(state["context_only"])
        self.assertEqual(data, b"new\n")
        self.assertEqual(source.read(1024)[0]["state"], "empty")

    def test_truncation_replacement_and_overwrite_start_new_context(self):
        for kind in ("truncated", "replaced", "overwritten"):
            with self.subTest(kind=kind):
                self.path.write_bytes(b"abcdefghij")
                source = LocalLog(self.path)
                source.read(1024)
                if kind == "replaced":
                    replacement = self.root / "replacement"
                    replacement.write_bytes(b"new")
                    replacement.replace(self.path)
                elif kind == "truncated":
                    self.path.write_bytes(b"new")
                else:
                    self.path.write_bytes(b"ABCDEFGHIJnew")
                state, _ = source.read(1024)
                self.assertEqual(state["gap_reason"], kind)
                self.assertTrue(state["context_only"])

    def test_poll_overrun_reports_dropped_bytes(self):
        self.path.write_bytes(b"")
        source = LocalLog(self.path)
        source.read(4)
        self.path.write_bytes(b"123456789")
        state, data = source.read(4)
        self.assertEqual(data, b"6789")
        self.assertEqual(state["skipped_bytes"], 5)
        self.assertEqual(state["state"], "gap")

    def test_remote_snapshot_preserves_bytes_and_bounds(self):
        self.path.write_bytes(b"old" + bytes(range(256)))
        state, data = remote_log(LocalShell(), str(self.path), 256)
        self.assertEqual(state["state"], "snapshot")
        self.assertEqual(data, bytes(range(256)))
        self.assertEqual(state["byte_start"], 3)
        self.assertTrue(state["context_only"])

    def test_missing_serial_does_not_prevent_remote_application_log(self):
        self.path.write_bytes(b"application evidence\n")
        output = self.root / "output"
        output.mkdir()
        profile = {"name": "fixture", "connection": {"type": "ssh"}, "logs": [
            {"name": "serial", "kind": "local", "path": str(self.root / "missing")},
            {"name": "application", "kind": "remote", "path": str(self.path)}]}
        collector = Collector(profile, output, connector=lambda _: LocalShell())
        try:
            cycle = collector.tick()
            self.assertEqual(cycle["sources"][0]["state"], "unavailable")
            self.assertEqual(cycle["sources"][1]["state"], "snapshot")
            self.assertEqual((output / cycle["sources"][1]["file"]).read_bytes(), b"application evidence\n")
            self.assertTrue((output / "diagnostics.json").exists())
        finally:
            collector.close()
