import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from embedded_linux.profile import ToolError
from embedded_linux.transfer import put_file, serve_one_file
from support import LocalShell


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "input"
        self.source.write_bytes(bytes(range(256)) * 32)
        self.profile = {"connection": {"type": "telnet", "host": "127.0.0.1"},
                        "transfer": {"method": "http", "bind_address": "127.0.0.1"}}

    def tearDown(self):
        self.temporary.cleanup()

    def test_http_serves_only_the_selected_file(self):
        with serve_one_file(self.source, "127.0.0.1") as url:
            with urllib.request.urlopen(url) as response:
                self.assertEqual(response.read(), self.source.read_bytes())
            with self.assertRaises(urllib.error.HTTPError) as failure:
                urllib.request.urlopen(url + "/../input")
            self.assertEqual(failure.exception.code, 404)

    def test_verified_upload_and_mode(self):
        target = self.root / "target with space"
        result = put_file(LocalShell(), self.profile, self.source, str(target), executable=True)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual(result["size"], self.source.stat().st_size)

    def test_hash_failure_does_not_replace_destination(self):
        class CorruptHash(LocalShell):
            def execute(self, command, **kwargs):
                if command.startswith("sha256sum "):
                    return 0, "incorrect checksum"
                return super().execute(command, **kwargs)
        target = self.root / "target"
        target.write_bytes(b"preserve me")
        with self.assertRaises(ToolError):
            put_file(CorruptHash(), self.profile, self.source, str(target))
        self.assertEqual(target.read_bytes(), b"preserve me")
