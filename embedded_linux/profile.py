"""Local target configuration. Credentials are references, never profile values."""

import json
import math
import os
import re
import stat
from pathlib import Path


class ToolError(Exception):
    """An actionable configuration, connection or verification failure."""


def load_profile(path):
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ToolError("profile must be an object with version: 1")
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        raise ToolError("profile requires a target name")
    connection = value.get("connection", {})
    if not isinstance(connection, dict):
        raise ToolError("connection must be an object")
    if connection.get("type") not in ("ssh", "telnet", "serial"):
        raise ToolError("connection.type must be ssh, telnet or serial")
    if "password" in connection:
        raise ToolError("use password_file; do not store a password in the profile")
    if connection["type"] == "ssh" and "password_file" in connection:
        raise ToolError("SSH uses your SSH config/agent; password_file is for Telnet/serial consoles")
    if connection["type"] == "serial" and not connection.get("device"):
        raise ToolError("serial connection requires a device path")
    for field in ("device", "password_file", "config_file"):
        if field in connection and (not isinstance(connection[field], str) or not connection[field]):
            raise ToolError("connection." + field + " must be a nonempty path string")
    if connection["type"] != "serial":
        host = connection.get("host", "")
        if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:@-]*", host):
            raise ToolError("connection.host must be a hostname, SSH alias or IP address")
    if "user" in connection and (not isinstance(connection["user"], str) or
                                 not re.fullmatch(r"[A-Za-z0-9_.-]+", connection["user"])):
        raise ToolError("invalid connection.user")
    port = connection.get("port")
    if port is not None and (type(port) is not int or not 1 <= port <= 65535):
        raise ToolError("connection.port must be between 1 and 65535")
    timeout = connection.get("timeout", 10)
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ToolError("connection.timeout must be a finite positive number")
    for field in ("shell_prompt", "login_prompt", "password_prompt"):
        if field in connection:
            if not isinstance(connection[field], str):
                raise ToolError(field + " must be a regular expression string")
            try:
                re.compile(connection[field])
            except re.error as exc:
                raise ToolError(field + " is not a valid regular expression") from exc
    for field in ("logs", "probes"):
        if not isinstance(value.get(field, []), list):
            raise ToolError(field + " must be an array")
    for entry in value.get("logs", []):
        if (not isinstance(entry, dict) or
                not isinstance(entry.get("name"), str) or
                not re.fullmatch(r"[A-Za-z0-9_-]+", entry["name"]) or
                entry.get("kind") not in ("local", "remote") or
                not isinstance(entry.get("path"), str)):
            raise ToolError("each log needs a simple name, local/remote kind and path")
    names = [entry["name"] for entry in value.get("logs", [])]
    if len(names) != len(set(names)):
        raise ToolError("log names must be unique")
    for probe in value.get("probes", []):
        if (not isinstance(probe, dict) or not isinstance(probe.get("name"), str) or
                not re.fullmatch(r"[A-Za-z0-9_-]+", probe["name"]) or
                not isinstance(probe.get("command"), str)):
            raise ToolError("each probe needs a simple name and a shell command")
    probe_names = [probe["name"] for probe in value.get("probes", [])]
    if len(probe_names) != len(set(probe_names)) or "identity" in probe_names:
        raise ToolError("probe names must be unique; identity is reserved")
    identity = value.get("identity")
    if "identity" in value and (not isinstance(identity, dict) or
                                not isinstance(identity.get("command"), str) or not identity["command"] or
                                not isinstance(identity.get("contains"), str) or not identity["contains"]):
        raise ToolError("identity requires command and a nonempty contains value")
    debugger = value.get("gdb", {})
    if not isinstance(debugger, dict):
        raise ToolError("gdb must be an object")
    if "auto_solib_add" in debugger and type(debugger["auto_solib_add"]) is not bool:
        raise ToolError("gdb.auto_solib_add must be true or false")
    if "native" in debugger and (not isinstance(debugger["native"], str) or not debugger["native"]):
        raise ToolError("gdb.native must name the target debugger")
    transfer = value.get("transfer", {})
    if not isinstance(transfer, dict) or transfer.get("method", "sftp") not in ("sftp", "scp", "ssh-stream", "http"):
        raise ToolError("transfer.method must be sftp, scp, ssh-stream or http")
    deployment = value.get("deploy", {})
    if not isinstance(deployment, dict):
        raise ToolError("deploy must be an object")
    if "argv" in deployment and (not isinstance(deployment["argv"], list) or
                                 not deployment["argv"] or
                                 not all(isinstance(arg, str) for arg in deployment["argv"])):
        raise ToolError("deploy.argv must be a nonempty array of strings")
    for field in ("cwd", "verify_command"):
        if field in deployment and not isinstance(deployment[field], str):
            raise ToolError("deploy." + field + " must be a string")
    return value


def password_from_file(path):
    path = Path(path).expanduser()
    with path.open("r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                stat.S_IMODE(info.st_mode) != 0o600):
            raise ToolError("password_file must be a regular file owned by you with mode 0600")
        value = stream.read().rstrip("\r\n")
    if not value or "\n" in value or "\r" in value:
        raise ToolError("password_file must contain exactly one nonempty line")
    return value
