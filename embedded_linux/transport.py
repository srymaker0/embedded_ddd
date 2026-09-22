"""SSH commands and POSIX shell consoles with bounded, framed responses."""

import re
import secrets
import shlex
import subprocess
import time
from pathlib import Path

from .profile import ToolError, password_from_file


class CommandError(ToolError):
    def __init__(self, returncode, output):
        self.returncode = returncode
        self.output = output
        super().__init__("remote command exited {}: {}".format(returncode, output[-2000:]))


class ConnectionLost(ToolError):
    """Command outcome is unknown: never automatically replay a mutation."""


class SSH:
    def __init__(self, config):
        self.config = config
        self.destination = ((config["user"] + "@") if config.get("user") else "") + config["host"]

    def options(self, scp=False):
        result = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                  "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2"]
        if self.config.get("port"):
            result += ["-P" if scp else "-p", str(self.config["port"])]
        if self.config.get("config_file"):
            result += ["-F", str(Path(self.config["config_file"]).expanduser())]
        return result

    def execute(self, command, timeout=15, check=True, input_data=None):
        argv = ["ssh", "-T"] + self.options() + [self.destination, "sh -c " + shlex.quote(command)]
        try:
            result = subprocess.run(argv, input=input_data or b"", stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ConnectionLost("SSH timed out; remote command outcome is unknown") from exc
        if result.returncode == 255:
            raise ConnectionLost("SSH connection failed: " + result.stderr.decode("utf-8", "replace"))
        output = result.stdout.decode("utf-8", "replace")
        if check and result.returncode:
            raise CommandError(result.returncode, output + result.stderr.decode("utf-8", "replace"))
        return result.returncode, output

    def close(self):
        pass


class Console:
    """One Telnet or serial shell. It never owns a console log's serial port."""

    def __init__(self, config, child=None):
        try:
            import pexpect
        except ImportError as exc:
            raise ToolError("console support requires pip install '.[console]' in the tool environment") from exc
        self.pexpect = pexpect
        self.child = child
        self.serial = None
        self.closed = False
        self.config = config
        try:
            if self.child is None:
                if config["type"] == "telnet":
                    self.child = pexpect.spawn("telnet", [config["host"], str(config.get("port", 23))],
                                              encoding="utf-8", codec_errors="replace", echo=False)
                else:
                    self._open_serial(config)
                self._login(config)
            self.execute("true", timeout=config.get("timeout", 10))
        except pexpect.ExceptionPexpect as exc:
            self.close()
            raise ConnectionLost("console connection failed: " + str(exc)) from exc
        except BaseException:
            self.close()
            raise

    def _open_serial(self, config):
        try:
            import serial
            from pexpect.fdpexpect import fdspawn
        except ImportError as exc:
            raise ToolError("direct serial support requires pip install '.[serial]'") from exc
        # exclusive prevents two cooperating readers; do not open a port held by a terminal app.
        self.serial = serial.Serial(config["device"], config.get("baud", 115200),
                                    timeout=0, write_timeout=5, exclusive=True)
        self.child = fdspawn(self.serial.fileno(), encoding="utf-8", codec_errors="replace")

    def _login(self, config):
        login = config.get("login_prompt", r"(?i)login:\s*$")
        password = config.get("password_prompt", r"(?i)password:\s*$")
        shell = config.get("shell_prompt", r"(?m)[^\r\n]*[#$] ?$")
        if config["type"] == "serial":
            self.child.sendline("")
        try:
            for _ in range(4):
                index = self.child.expect([login, password, shell], timeout=config.get("timeout", 10))
                if index == 0:
                    if not config.get("user"):
                        raise ToolError("console requested login but connection.user is absent")
                    self.child.sendline(config["user"])
                elif index == 1:
                    if not config.get("password_file"):
                        raise ToolError("console requested a password; configure password_file")
                    # Pexpect logging is deliberately disabled: credentials must never enter artifacts.
                    self.child.sendline(password_from_file(config["password_file"]))
                else:
                    return
        except (self.pexpect.EOF, self.pexpect.TIMEOUT) as exc:
            raise ConnectionLost("console login failed or timed out") from exc
        raise ToolError("console login did not reach a shell")

    def execute(self, command, timeout=15, check=True, input_data=None):
        if input_data is not None:
            raise ToolError("binary stdin is supported only over SSH; choose HTTP for console uploads")
        if self.closed:
            raise ConnectionLost("console is closed")
        token = secrets.token_hex(12)
        begin, end = "EL_BEGIN_" + token, "EL_END_" + token
        # Split markers in the echoed command so only actual output can match them.
        # A subshell keeps 'exit', cd and variable changes from escaping the command.
        wire = ("printf '\\nEL_BEGIN_%s\\n' {token}; sh -c {command}; "
                "__el_status=$?; printf '\\nEL_END_%s:%s\\n' {token} \"$__el_status\"").format(
                    token=token, command=shlex.quote(command))
        try:
            deadline = time.monotonic() + timeout
            self.child.sendline(wire)
            self.child.expect(re.escape(begin) + r"\r?\n", timeout=max(0, deadline - time.monotonic()))
            self.child.expect(re.escape(end) + r":([0-9]+)\r?\n", timeout=max(0, deadline - time.monotonic()))
            output = self.child.before.replace("\r\n", "\n")
            if output.endswith("\n"):
                output = output[:-1]  # framing newline, not command output
            returncode = int(self.child.match.group(1))
        except (self.pexpect.EOF, self.pexpect.TIMEOUT, OSError) as exc:
            self.close()  # A late marker must never be consumed by a later command.
            raise ConnectionLost("console disconnected or timed out; command outcome is unknown") from exc
        if check and returncode:
            raise CommandError(returncode, output)
        return returncode, output

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.child is not None:
            # fdspawn shares the serial fd: let pyserial close its own resource.
            if self.serial is None:
                self.child.close(force=True)
            else:
                self.serial.close()


def connect(profile):
    config = profile["connection"]
    return SSH(config) if config["type"] == "ssh" else Console(config)
