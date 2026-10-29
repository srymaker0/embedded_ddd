#!/usr/bin/env python3
"""Disposable localhost SSH target used by the DDD demo and agent evaluations."""

import argparse
import hashlib
import json
import os
import pwd
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from embedded_linux.debug import process_state
from embedded_linux.logs import write_json
from embedded_linux.profile import ToolError
from embedded_linux.transport import SSH

SCRIPT = Path(__file__).resolve()


def wait_until(predicate, description, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise ToolError("timed out waiting for " + description)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def start_ticks(pid):
    try:
        return Path("/proc/{}/stat".format(pid)).read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def read_receipt(root):
    path = root / "receipt.json"
    return json.loads(path.read_text()) if path.exists() else None


def owned_process(root):
    receipt = read_receipt(root)
    if receipt and start_ticks(receipt["pid"]) == receipt["start_ticks"]:
        executable = Path("/proc/{}/exe".format(receipt["pid"]))
        try:
            if executable.resolve(strict=True) == root / "current-app":
                return receipt["pid"]
        except FileNotFoundError:
            pass
    return None


def stop_app(root):
    pid = owned_process(root)
    if pid:
        os.kill(pid, signal.SIGTERM)
        try:
            wait_until(lambda: owned_process(root) is None, "example application exit", timeout=3)
        except ToolError:
            if owned_process(root) == pid:
                os.kill(pid, signal.SIGKILL)
            wait_until(lambda: owned_process(root) is None, "example application cleanup", timeout=3)


def install(root, artifact):
    if artifact.parent != root or not artifact.is_file():
        raise ToolError("the lab installer only accepts staged files in its own directory")
    version = subprocess.check_output([str(artifact), "--version"], timeout=5, text=True).strip()
    stop_app(root)
    (root / "status.txt").unlink(missing_ok=True)
    shutil.copy2(str(artifact), str(root / "next-app"))
    (root / "next-app").replace(root / "current-app")
    # A remote project installer owns application startup, independent of the SSH client.
    with (root / "application.log").open("ab") as stream:
        app = subprocess.Popen([str(root / "current-app")], cwd=str(root),
                               stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                               start_new_session=True)
    receipt = {"pid": app.pid, "start_ticks": start_ticks(app.pid), "version": version,
               "sha256": digest(root / "current-app")}
    write_json(root / "receipt.json", receipt)
    with (root / "installations.jsonl").open("a") as stream:
        stream.write(json.dumps(receipt) + "\n")
    wait_until(lambda: (root / "status.txt").exists(), "application startup")
    if app.poll() is not None:
        raise ToolError("example application exited during startup")
    print(json.dumps(receipt))


def verify(root):
    receipt = read_receipt(root)
    expected = json.loads((root / "expected.json").read_text())
    pid = owned_process(root)
    if not pid or receipt["sha256"] != expected["sha256"] or digest(root / "current-app") != expected["sha256"]:
        raise ToolError("installed artifact does not match expected receipt")
    before = (root / "status.txt").read_text()
    after = wait_until(lambda: (root / "status.txt").read_text() != before, "a new heartbeat", timeout=2)
    del after
    status = (root / "status.txt").read_text()
    if "state=running" not in status or "version=" + expected["version"] not in status:
        raise ToolError("application has not recovered")
    print(json.dumps({"receipt": receipt, "status": status.strip()}))


class LinuxLab:
    """Owns one temporary SSH server and only the application named by its receipt."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.server = None
        self.server_log = None
        self.private = None
        self.profile = None

    def __enter__(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        try:
            for tool in ("sshd", "ssh", "ssh-keygen", "sftp", "gcc", "gdb", "timeout"):
                if not shutil.which(tool):
                    raise ToolError("Linux lab requires " + tool + "; see examples/README.md")
            (self.root / "lab.identity").write_text("embedded-ddd disposable Linux lab\n")
            self.private = tempfile.TemporaryDirectory(prefix="embedded-ddd-keys-")
            keys = Path(self.private.name)
            for name in ("host", "client"):
                subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(keys / name)],
                               check=True, timeout=10)
            (keys / "authorized_keys").write_bytes((keys / "client.pub").read_bytes())
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            config = keys / "sshd.conf"
            config.write_text("\n".join([
                "Port " + str(port), "ListenAddress 127.0.0.1", "HostKey " + str(keys / "host"),
                "PidFile " + str(keys / "sshd.pid"), "AuthorizedKeysFile " + str(keys / "authorized_keys"),
                "StrictModes no", "PasswordAuthentication no", "KbdInteractiveAuthentication no",
                "UsePAM no", "AllowUsers " + pwd.getpwuid(os.getuid()).pw_name,
                "Subsystem sftp internal-sftp", "AllowTcpForwarding no", "X11Forwarding no"]) + "\n")
            self.server_log = (self.root / "sshd.log").open("wb")
            self.server = subprocess.Popen([shutil.which("sshd"), "-D", "-e", "-f", str(config)],
                                           stdout=self.server_log, stderr=self.server_log)

            def listening():
                if self.server.poll() is not None:
                    raise ToolError((self.root / "sshd.log").read_text())
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        return True
                except OSError:
                    return False
            wait_until(listening, "localhost SSH listener")
            (keys / "known_hosts").write_text("[127.0.0.1]:{} {}".format(port, (keys / "host.pub").read_text()))
            client = keys / "ssh.conf"
            client.write_text("\n".join([
                "Host ddd-lab", "  HostName 127.0.0.1", "  Port " + str(port),
                "  User " + pwd.getpwuid(os.getuid()).pw_name,
                "  IdentityFile " + str(keys / "client"), "  IdentitiesOnly yes",
                "  UserKnownHostsFile " + str(keys / "known_hosts"), "  StrictHostKeyChecking yes"]) + "\n")
            self.profile = {"version": 1, "name": "disposable-linux-lab",
                            "connection": {"type": "ssh", "host": "ddd-lab", "config_file": str(client)},
                            "identity": {"command": "cat " + shlex.quote(str(self.root / "lab.identity")),
                                         "contains": "embedded-ddd disposable Linux lab"},
                            "transfer": {"method": "sftp"},
                            "logs": [{"name": "serial", "kind": "local", "path": str(self.root / "absent-serial.log")},
                                     {"name": "application", "kind": "remote", "path": str(self.root / "application.log")}],
                            "probes": [{"name": "receipt", "command": "cat " + shlex.quote(str(self.root / "receipt.json"))}],
                            "gdb": {"native": shutil.which("gdb")}}
            for version in ("1", "2"):
                subprocess.run(["gcc", "-g", "-O0", '-DLAB_VERSION="' + version + '"',
                                str(SCRIPT.with_name("linux_lab_app.c")), "-o", str(self.root / ("build-v" + version))],
                               check=True, timeout=30)
            (self.root / "application.log").touch()
            self.select_version("1")
            return self
        except BaseException:
            self.close()
            raise

    def control_command(self, action, *extra):
        return " ".join(shlex.quote(arg) for arg in
                        [sys.executable, str(SCRIPT), "control", action, "--root", str(self.root), *extra])

    def select_version(self, version):
        self.version = version
        build = self.root / ("build-v" + version)
        write_json(self.root / "expected.json", {"version": version, "sha256": digest(build)})
        self.profile["deploy"] = {
            "cwd": str(self.root),
            "argv": [sys.executable, "-m", "embedded_linux.cli", "--profile", str(self.root / "board.local.json"),
                     "exec", self.control_command("install", "--artifact", str(self.root / "staged-app"))],
            "verify_command": self.control_command("verify")}
        write_json(self.root / "board.local.json", self.profile)

    def cli(self, *args, check=True):
        result = subprocess.run([sys.executable, "-m", "embedded_linux.cli", "--profile",
                                 str(self.root / "board.local.json"), *map(str, args)],
                                cwd=str(self.root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=90)
        if check and result.returncode:
            raise ToolError("helper failed: " + result.stderr + result.stdout)
        return result

    def deploy(self, name):
        transfer = self.cli("put", self.root / ("build-v" + self.version), self.root / "staged-app", "--executable")
        write_json(self.root / (name + "-transfer.json"), json.loads(transfer.stdout))
        result = self.cli("deploy", "--output", self.root / name, "--interval", "0.1", "--observe", "0.2", "--timeout", "30")
        return json.loads(result.stdout)

    def state(self):
        session = SSH(self.profile["connection"])
        try:
            return process_state(session, read_receipt(self.root)["pid"])
        finally:
            session.close()

    def signal_app(self, value, state):
        pid = owned_process(self.root)
        if not pid:
            raise ToolError("example process identity changed")
        self.cli("exec", "kill -{} {}".format(value, pid))
        wait_until(lambda: "state=" + state in (self.root / "status.txt").read_text(), state)

    def close(self):
        try:
            stop_app(self.root)
        finally:
            try:
                if self.server is not None:
                    self.server.terminate()
                    try:
                        self.server.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.server.kill()
                        self.server.wait(timeout=3)
            finally:
                if self.server_log:
                    self.server_log.close()
                if self.private:
                    self.private.cleanup()

    def __exit__(self, *_):
        self.close()


def demo(root):
    with LinuxLab(root) as lab:
        inspection = json.loads(lab.cli("inspect", "--for", "deploy").stdout)
        write_json(lab.root / "readiness.json", inspection)
        first = lab.deploy("deploy-v1")
        lab.select_version("2")
        second = lab.deploy("deploy-v2")
        lab.signal_app("USR1", "stalled")
        collection = json.loads(lab.cli("collect", "--output", lab.root / "diagnostics").stdout)
        before = lab.state()
        lab.cli("gdb-snapshot", "--pid", before["pid"], "--output", lab.root / "debug")
        snapshot = json.loads((lab.root / "debug/gdb-result.json").read_text())
        stack = (lab.root / "debug/gdb.txt").read_text()
        if "wait_for_recovery" not in stack or not snapshot["restored"]:
            raise ToolError("snapshot did not identify the blocked worker and verify detach")
        lab.signal_app("USR2", "running")
        recovery = json.loads(lab.cli("exec", lab.control_command("verify")).stdout)
        result = {"result": "passed", "target": "disposable localhost Linux process",
                  "deployments": [first["verification"], second["verification"]],
                  "collection": collection["coverage"], "blocked_frame": "wait_for_recovery",
                  "debugger_detached": snapshot["restored"], "recovery": recovery,
                  "limitations": ["Simulated stalled worker; no physical board, serial hardware or firmware flashing."]}
    result["cleanup"] = "application stopped, SSH server stopped, temporary keys removed"
    write_json(Path(root).resolve() / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--output", required=True, help="new directory for evidence")
    control = commands.add_parser("control", help="internal example installer and acceptance entrypoint")
    control.add_argument("action", choices=("install", "verify"))
    control.add_argument("--root", required=True)
    control.add_argument("--artifact")
    args = parser.parse_args()
    try:
        if args.command == "run":
            print(json.dumps(demo(args.output), indent=2))
        else:
            root = Path(args.root).resolve()
            if (root / "lab.identity").read_text().strip() != "embedded-ddd disposable Linux lab":
                raise ToolError("not an example workspace")
            if args.action == "install":
                if not args.artifact:
                    raise ToolError("--artifact is required for install")
                install(root, Path(args.artifact).resolve())
            else:
                verify(root)
        return 0
    except (ToolError, OSError, subprocess.SubprocessError) as exc:
        print("linux-lab: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
