"""Read-only readiness checks scoped to the operation the user intends to run."""

import importlib.util
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from .logs import LocalLog, check_identity, remote_log
from .profile import ToolError, password_from_file
from .transport import connect


def inspect_profile(profile, purpose="connect", local=False, connector=connect):
    report = {"target": profile["name"], "operation": purpose,
              "scope": "host" if local else "host_and_target", "checks": [],
              "limitations": ["Readiness is not application health or deployment acceptance."]}

    def record(name, status, detail):
        report["checks"].append({"name": name, "status": status, "detail": detail})

    def attempt(name, operation, failure="failed"):
        try:
            detail = operation()
            record(name, "passed", detail)
            return True
        except (ToolError, OSError, subprocess.TimeoutExpired) as exc:
            record(name, failure, str(exc))
            return False

    def host_tool(name):
        path = shutil.which(name)
        record("host:" + name, "passed" if path else "failed", path or "install " + name)

    connection = profile["connection"]
    kind = connection["type"]
    if kind in ("ssh", "telnet"):
        host_tool(kind)
    modules = [] if kind == "ssh" else ["pexpect"]
    if kind == "serial":
        modules.append("serial")
        device = Path(connection["device"]).expanduser()
        ok = device.is_char_device() and os.access(str(device), os.R_OK | os.W_OK)
        record("host:serial-device", "passed" if ok else "failed",
               "accessible character device" if ok else "check the serial path and permissions")
        report["limitations"].append("Opening a serial console may reset some devices; --local never opens it.")
    for module in modules:
        ok = importlib.util.find_spec(module) is not None
        record("host:" + module, "passed" if ok else "failed",
               "available" if ok else "install the helper's console/serial extra")
    if connection.get("config_file"):
        def read_config():
            with Path(connection["config_file"]).expanduser().open("rb") as stream:
                stream.read(1)
            return "SSH configuration is readable"
        attempt("host:ssh-config", read_config)
    if connection.get("password_file"):
        def read_password():
            password_from_file(connection["password_file"])
            return "private password reference is readable; value omitted"
        attempt("host:password-file", read_password)

    if purpose == "deploy":
        deployment = profile.get("deploy", {})
        cwd = Path(deployment.get("cwd", ".")).expanduser().resolve()
        record("deploy:cwd", "passed" if cwd.is_dir() else "failed", str(cwd))
        argv = deployment.get("argv", [])
        executable = argv[0] if argv else ""
        if executable and "/" in executable:
            executable = str(cwd / executable)
        found = shutil.which(executable) if executable else None
        record("deploy:installer", "passed" if found else "failed",
               found or "configure deploy.argv with an existing executable")
        verify = bool(deployment.get("verify_command"))
        record("deploy:verification", "passed" if verify else "warning",
               "configured, not executed" if verify else "no project acceptance command configured")
        report["limitations"].append("Installer arguments, update semantics and verification are not executed.")

    method = profile.get("transfer", {}).get("method", "sftp" if kind == "ssh" else "http")
    if purpose == "put":
        if method != "http" and kind != "ssh":
            record("put:transport", "failed", method + " requires an SSH connection")
        if method in ("sftp", "scp"):
            host_tool(method)
        if method == "http" and not profile.get("transfer", {}).get("bind_address") and kind == "serial":
            record("put:http-address", "failed", "serial HTTP transfer needs transfer.bind_address")
        report["limitations"].append("No file transferred; destination space, permissions and transfer reachability remain unverified.")

    if purpose == "gdb-snapshot" and not profile.get("gdb", {}).get("native"):
        record("gdb:native", "failed", "configure gdb.native with a matching target executable")

    if purpose in ("collect", "deploy") and not profile.get("logs"):
        record("logs", "failed", "configure at least one log; use project tools for journal-only targets")

    def failed():
        return any(check["status"] == "failed" for check in report["checks"])

    session = None
    if not local and not failed():
        try:
            session = connector(profile)
            check_identity(session, profile)
            record("target:identity", "passed" if profile.get("identity") else "warning",
                   "matched configured identity" if profile.get("identity") else
                   "no expected identity configured; confirm the target before mutations")
            _, identity = session.execute("uname -srmo && cat /proc/sys/kernel/random/boot_id", timeout=10)
            record("target:linux", "passed", identity.strip())

            def target_tool(tool):
                def probe():
                    _, text = session.execute("command -v " + shlex.quote(tool), timeout=10)
                    return text.strip()
                attempt("target:" + tool, probe)

            if purpose in ("collect", "deploy"):
                available = 0
                for entry in profile.get("logs", []):
                    def read_log():
                        if entry["kind"] == "local":
                            _, data = LocalLog(entry["path"]).read(256)
                        else:
                            _, data = remote_log(session, entry["path"], 256)
                        return "readable, {} sampled bytes; content omitted".format(len(data))
                    available += attempt("log:" + entry["name"], read_log, failure="warning")
                record("logs", "passed" if available else "failed",
                       "{} of {} sources readable".format(available, len(profile.get("logs", []))))
            if purpose == "put":
                for tool in ["sha256sum", "chmod", "mv"] + (["cat"] if method == "ssh-stream" else
                                                              ["scp"] if method == "scp" else []):
                    target_tool(tool)
                if method == "http":
                    attempt("target:http-client", lambda: session.execute(
                        "command -v curl || command -v wget", timeout=10)[1].strip())
            if purpose == "gdb-snapshot":
                debugger = profile["gdb"]["native"]
                def gdb_version():
                    _, text = session.execute(shlex.quote(debugger) + " --version", timeout=10)
                    if not text.startswith("GNU gdb "):
                        raise ToolError("configured executable did not identify itself as native GDB")
                    return text.splitlines()[0]
                attempt("target:gdb", gdb_version)
                attempt("target:timeout", lambda: session.execute("timeout -s TERM 1 true", timeout=5)[1])
                for tool in ("sha256sum", "readlink"):
                    target_tool(tool)
                report["limitations"].append("No process attached; PID identity, ptrace permissions and symbol matching remain unverified.")
        except (ToolError, OSError, subprocess.TimeoutExpired) as exc:
            record("target:connection", "failed", str(exc))
        finally:
            if session is not None:
                session.close()
    elif local:
        report["limitations"].append("Target connection, identity and capabilities have not been checked.")
    report["checks_passed"] = not failed()
    report["ready"] = None if local else not failed()
    return report
