"""Native GDB snapshots. Function calls and arbitrary memory writes stay explicit."""

import shlex
import time

from .logs import check_identity, save_bytes, write_json
from .profile import ToolError
from .transport import connect


def process_state(session, pid):
    _, output = session.execute(
        "cat /proc/{p}/stat; printf '\\nEL_STATUS\\n'; cat /proc/{p}/status; "
        "printf '\\nEL_EXE\\n'; readlink /proc/{p}/exe".format(p=pid))
    try:
        stat_line, rest = output.split("\nEL_STATUS\n", 1)
        status, executable = rest.split("\nEL_EXE\n", 1)
        fields = stat_line.strip().rsplit(")", 1)[1].split()
        tracer = next(line.split(":", 1)[1].strip() for line in status.splitlines()
                      if line.startswith("TracerPid:"))
        return {"pid": pid, "start_ticks": fields[19], "state": fields[0],
                "tracer_pid": int(tracer), "executable": executable.strip()}
    except (IndexError, ValueError, StopIteration) as exc:
        raise ToolError("could not parse process identity from /proc") from exc


def native_snapshot(profile, pid, output, timeout=15, connector=connect):
    if pid <= 1:
        raise ToolError("choose a specific application PID greater than 1")
    debugger = profile.get("gdb", {}).get("native")
    if not debugger:
        raise ToolError("configure gdb.native with the target's GDB executable path")
    result = {"target": profile["name"], "pid": pid, "started_at": time.time(),
              "result": "not_started", "restored": False}
    session = None
    try:
        session = connector(profile)
        check_identity(session, profile)
        before = process_state(session, pid)
        result["before"] = before
        if before["tracer_pid"] or before["state"] in ("T", "t", "Z", "X"):
            raise ToolError("target is already traced, stopped or exiting; no attachment attempted")
        _, version = session.execute(shlex.quote(debugger) + " --version")
        save_bytes(output / "gdb-version.txt", version.encode("utf-8"))
        session.execute("command -v timeout >/dev/null")
        _, digest = session.execute("sha256sum /proc/{}/exe".format(pid))
        result["executable_sha256"] = digest.split()[0]
        # Recheck after preflight, since the service may have restarted in between.
        if process_state(session, pid)["start_ticks"] != before["start_ticks"]:
            raise ToolError("process changed during preflight")
        commands = ["set pagination off", "set confirm off", "info sharedlibrary",
                    "info threads", "thread apply all bt 8", "detach", "echo EL_GDB_DETACHED\\n"]
        argv = ["timeout", "-s", "TERM", str(timeout), debugger, "--nx", "--nh", "--batch", "-q",
                "-iex", "set auto-load off"]
        if profile.get("gdb", {}).get("auto_solib_add") is False:
            argv += ["-iex", "set auto-solib-add off"]
            result["symbols"] = "shared-library symbols not automatically loaded"
        argv += ["-p", str(pid)]
        for command in commands:
            argv += ["-ex", command]
        result["result"] = "outcome_unknown"
        write_json(output / "gdb-result.json", result)
        code, text = session.execute(" ".join(shlex.quote(arg) for arg in argv) + " 2>&1",
                                     timeout=timeout + 8, check=False)
        save_bytes(output / "gdb.txt", text.encode("utf-8"))
        result.update(returncode=code, detached_marker="EL_GDB_DETACHED" in text,
                      result="snapshot_collected" if code == 0 and "EL_GDB_DETACHED" in text else "failed")
    except (ToolError, OSError) as exc:
        result["error"] = str(exc)
    finally:
        if session:
            session.close()
        # A successful GDB exit alone is insufficient; verify the same process is untraced.
        if result["result"] != "not_started":
            verification = None
            try:
                verification = connector(profile)
                after = process_state(verification, pid)
                result["after"] = after
                result["restored"] = (after["start_ticks"] == result["before"]["start_ticks"] and
                                      after["tracer_pid"] == 0 and after["state"] not in ("T", "t", "Z", "X"))
            except (ToolError, OSError) as exc:
                result["restore_error"] = str(exc)
            finally:
                if verification:
                    verification.close()
        if result["result"] == "snapshot_collected" and not result["restored"]:
            result["result"] = "outcome_unknown"
        result["finished_at"] = time.time()
        write_json(output / "gdb-result.json", result)
    return result
