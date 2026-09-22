"""Command line entry points; profile commands remain owned by the target project."""

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .debug import native_snapshot
from .logs import Collector, check_identity, write_json
from .profile import ToolError, load_profile
from .transfer import put_file
from .transport import connect


def output_directory(path):
    path = Path(path).expanduser()
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    return path


def stop_owned_process(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def collect(profile, args):
    output = output_directory(args.output)
    collector = Collector(profile, output, args.max_bytes)
    deadline = time.monotonic() + args.duration
    try:
        while True:
            collector.tick()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(args.interval, remaining))
    finally:
        collector.close()
    sources = [source for cycle in collector.report["cycles"] for source in cycle["sources"]]
    available = [s for s in sources if s["state"] != "unavailable"]
    result = {"output": str(output), "coverage": "none" if not available else
              "partial" if len(available) != len(sources) else "complete",
              "meaning": "evidence collected; application health is not inferred"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if available else 2


def deploy(profile, args):
    deployment = profile.get("deploy", {})
    argv = deployment.get("argv")
    if (not isinstance(argv, list) or not argv or
            not all(isinstance(item, str) for item in argv)):
        raise ToolError("configure deploy.argv as the project's existing deployment command")
    cwd = Path(deployment.get("cwd", ".")).expanduser().resolve()
    output = output_directory(args.output)
    collector = Collector(profile, output, args.max_bytes)
    result = {"target": profile["name"], "started_at": time.time(), "result": "not_started"}
    process = None
    try:
        collector.connection()  # The collector checks configured identity on each connection.
        collector.tick()  # Record the log boundary before launching any deployment.
        write_json(output / "deployment.json", result)
        with (output / "deploy.log").open("wb") as stream:
            os.chmod(str(output / "deploy.log"), 0o600)
            process = subprocess.Popen(argv, cwd=str(cwd), stdout=stream, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            result["result"] = "running"
            write_json(output / "deployment.json", result)
            deadline = time.monotonic() + args.timeout
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    result["result"] = "outcome_unknown"
                    stop_owned_process(process)
                    break
                time.sleep(min(args.interval, max(0, deadline - time.monotonic())))
                collector.tick()
            result["returncode"] = process.returncode
            if result["result"] == "running":
                result["result"] = "installer_succeeded" if process.returncode == 0 else "installer_failed"
        deadline = time.monotonic() + args.observe
        while True:
            collector.tick()
            if time.monotonic() >= deadline:
                break
            time.sleep(min(args.interval, max(0, deadline - time.monotonic())))
        # Only a project-owned check knows receipt, slot/version and service acceptance semantics.
        verify = deployment.get("verify_command")
        if verify and result["result"] == "installer_succeeded":
            code, text = collector.connection().execute(verify, timeout=15, check=False)
            from .logs import save_bytes
            save_bytes(output / "verify.txt", text.encode("utf-8"))
            result["verification"] = "passed" if code == 0 else "failed"
        else:
            result["verification"] = "not_run"
    except KeyboardInterrupt:
        result["result"] = "outcome_unknown" if process else "not_started"
        result["error"] = "cancelled; inspect target state before retrying"
        if process:
            stop_owned_process(process)
    except (ToolError, OSError) as exc:
        if process and process.poll() is None:
            stop_owned_process(process)
            result["result"] = "outcome_unknown"
        result["error"] = str(exc)
    finally:
        collector.close()
        result["finished_at"] = time.time()
        write_json(output / "deployment.json", result)
    print(json.dumps({**result, "output": str(output)}, ensure_ascii=False))
    return 0 if (result["result"] == "installer_succeeded" and
                 result.get("verification") != "failed" and not result.get("error")) else 2


def parser():
    root = argparse.ArgumentParser(description="embedded-ddd: Deploy, Diagnostics, Debug for embedded Linux.")
    root.add_argument("--profile", required=True, help="local target JSON; see examples")
    commands = root.add_subparsers(dest="action", required=True)
    commands.add_parser("inspect", help="read target identity and basic command availability")
    execute = commands.add_parser("exec", help="execute one explicit POSIX shell command; never retried")
    execute.add_argument("--timeout", type=int, default=15)
    execute.add_argument("command")
    upload = commands.add_parser("put", help="stage one file and verify SHA256 before rename")
    upload.add_argument("source")
    upload.add_argument("destination")
    upload.add_argument("--executable", action="store_true")
    upload.add_argument("--timeout", type=int, default=120)
    for name in ("collect", "deploy"):
        command = commands.add_parser(name, help="collect evidence" if name == "collect" else
                                      "run the configured deployment command with automatic observation")
        command.add_argument("--output", required=True, help="new directory; existing runs are never overwritten")
        command.add_argument("--interval", type=float, default=3)
        command.add_argument("--max-bytes", type=int, default=65536, help="per source per observation")
        if name == "collect":
            command.add_argument("--duration", type=float, default=0)
        else:
            command.add_argument("--timeout", type=int, default=1200)
            command.add_argument("--observe", type=float, default=15)
    debug = commands.add_parser("gdb-snapshot", help="briefly pause a PID, read stacks, detach and verify recovery")
    debug.add_argument("--pid", type=int, required=True)
    debug.add_argument("--output", required=True)
    debug.add_argument("--timeout", type=int, default=15)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        for field in ("timeout", "interval", "max_bytes"):
            if hasattr(args, field) and (not math.isfinite(getattr(args, field)) or getattr(args, field) <= 0):
                raise ToolError(field + " must be positive")
        for field in ("duration", "observe"):
            if hasattr(args, field) and (not math.isfinite(getattr(args, field)) or getattr(args, field) < 0):
                raise ToolError(field + " must be nonnegative")
        profile = load_profile(args.profile)
        if args.action == "collect":
            return collect(profile, args)
        if args.action == "deploy":
            return deploy(profile, args)
        if args.action == "gdb-snapshot":
            output = output_directory(args.output)
            result = native_snapshot(profile, args.pid, output, timeout=args.timeout)
            print(json.dumps({**result, "output": str(output)}, ensure_ascii=False))
            return 0 if result["result"] == "snapshot_collected" and result["restored"] else 2
        session = connect(profile)
        try:
            check_identity(session, profile)
            if args.action == "inspect":
                _, text = session.execute("uname -srmo; printf 'boot_id='; cat /proc/sys/kernel/random/boot_id; "
                                          "for t in sh stat tail base64 sha256sum timeout; do command -v \"$t\"; done")
                print(text)
            elif args.action == "exec":
                code, text = session.execute(args.command, timeout=args.timeout, check=False)
                print(text, end="")
                return code
            elif args.action == "put":
                print(json.dumps(put_file(session, profile, args.source, args.destination,
                                         args.executable, args.timeout)))
        finally:
            session.close()
        return 0
    except KeyboardInterrupt:
        print("embedded-ddd: collection cancelled; existing evidence retained", file=sys.stderr)
        return 130
    except (ToolError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("embedded-ddd: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
