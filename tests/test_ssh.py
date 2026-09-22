import os
import pwd
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from embedded_linux.transfer import put_file
from embedded_linux.transport import CommandError, SSH


@unittest.skipUnless(shutil.which("sshd") and shutil.which("ssh-keygen"), "requires local OpenSSH server")
class SSHIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.addClassCleanup(cls.temporary.cleanup)
        for name in ("host", "client"):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(cls.root / name)],
                           check=True, timeout=10)
        (cls.root / "authorized_keys").write_bytes((cls.root / "client.pub").read_bytes())
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        user = pwd.getpwuid(os.getuid()).pw_name
        sftp = "/usr/lib/openssh/sftp-server"
        config = cls.root / "sshd.conf"
        config.write_text("\n".join([
            "Port " + str(port), "ListenAddress 127.0.0.1", "HostKey " + str(cls.root / "host"),
            "PidFile " + str(cls.root / "sshd.pid"), "AuthorizedKeysFile " + str(cls.root / "authorized_keys"),
            "StrictModes no", "PasswordAuthentication no", "KbdInteractiveAuthentication no", "UsePAM no",
            "AllowUsers " + user, "Subsystem sftp " + sftp]) + "\n")
        log = (cls.root / "sshd.log").open("wb")
        cls.addClassCleanup(log.close)
        cls.server = subprocess.Popen([shutil.which("sshd"), "-D", "-e", "-f", str(config)],
                                      stdout=log, stderr=log)
        cls.addClassCleanup(cls.stop_server)
        deadline = time.monotonic() + 5
        while True:
            if cls.server.poll() is not None:
                raise RuntimeError((cls.root / "sshd.log").read_text())
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("fixture sshd did not listen")
                time.sleep(0.05)
        known_hosts = cls.root / "known_hosts"
        known_hosts.write_text("[127.0.0.1]:{} {}".format(port, (cls.root / "host.pub").read_text()))
        client_config = cls.root / "ssh.conf"
        client_config.write_text("\n".join([
            "Host embedded-fixture", "  HostName 127.0.0.1", "  Port " + str(port), "  User " + user,
            "  IdentityFile " + str(cls.root / "client"), "  IdentitiesOnly yes",
            "  UserKnownHostsFile " + str(known_hosts), "  StrictHostKeyChecking yes"]) + "\n")
        cls.profile = {"connection": {"type": "ssh", "host": "embedded-fixture", "config_file": str(client_config)}}
        cls.session = SSH(cls.profile["connection"])

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=3)

    def test_real_ssh_alias_authentication_quoting_and_status(self):
        self.assertEqual(self.session.execute("printf '%s' \"one 'two'\""), (0, "one 'two'"))
        with self.assertRaises(CommandError) as failure:
            self.session.execute("printf failure; exit 9")
        self.assertEqual(failure.exception.returncode, 9)
        self.assertEqual(failure.exception.output, "failure")

    def test_sftp_scp_legacy_and_ssh_stream(self):
        source = self.root / "payload with space"
        source.write_bytes(bytes(range(256)) * 32)
        for method in ("sftp", "scp", "ssh-stream"):
            with self.subTest(method=method):
                target = self.root / ("uploaded with space-" + method)
                profile = {**self.profile, "transfer": {"method": method}}
                put_file(self.session, profile, source, str(target))
                self.assertEqual(target.read_bytes(), source.read_bytes())
