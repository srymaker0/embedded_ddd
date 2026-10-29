#!/usr/bin/env python3
"""Run fresh Codex sessions against disposable Linux targets; uses model quota."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# The source distribution includes the example fixture, separate from the helper package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from linux_lab import LinuxLab, digest, read_receipt
from embedded_linux.logs import write_json
from embedded_linux.profile import ToolError, load_profile

REPOSITORY = Path(__file__).resolve().parents[1]
CASES = ("first-connection", "missing-serial", "installer-disconnect", "authorized-gdb")
SKILLS = ("embedded-linux-deploy", "embedded-linux-diagnostics", "embedded-linux-debug")


def command_evidence(events):
    """Only completed, successful tool output counts as evidence of reading a skill."""
    outputs = []
    for line in events.splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if (event.get("type") == "item.completed" and item.get("type") == "command_execution"
                and item.get("exit_code") == 0):
            outputs.append(item.get("aggregated_output", ""))
    return "\n".join(outputs)


def skill_was_read(outputs, skill):
    titles = {"embedded-linux-deploy": "# Embedded Linux deployment",
              "embedded-linux-diagnostics": "# Embedded Linux diagnostics",
              "embedded-linux-debug": "# Embedded Linux Debug"}
    return "name: " + skill in outputs and titles[skill] in outputs


def preserved_process(before, after):
    return (before["pid"] == after["pid"] and before["start_ticks"] == after["start_ticks"]
            and after["tracer_pid"] == 0 and after["state"] not in ("T", "t", "Z", "X"))


def trace_summary(events):
    summary = {"turn_completed": False, "usage": None, "last_agent_message": None}
    for line in events.splitlines():
        event = json.loads(line)
        if event.get("type") == "turn.completed":
            summary["turn_completed"] = True
            summary["usage"] = event.get("usage")
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            summary["last_agent_message"] = item.get("text")
    return summary


def run_codex(project, target, prompt, case_directory, timeout):
    (case_directory / "prompt.txt").write_text(prompt)
    argv = ["codex", "--ask-for-approval", "never", "exec", "--json", "--ephemeral",
            "--sandbox", "workspace-write", "-c", "sandbox_workspace_write.network_access=true",
            "--skip-git-repo-check", "--cd", str(project), "--add-dir", str(target),
            "--output-last-message", str(case_directory / "response.txt"), "-"]
    started = time.monotonic()
    timed_out = False
    with (case_directory / "events.jsonl").open("w") as events, (case_directory / "stderr.txt").open("w") as errors:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=events, stderr=errors,
                                   text=True, start_new_session=True)
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    summary = trace_summary((case_directory / "events.jsonl").read_text())
    response = case_directory / "response.txt"
    if not response.exists() and summary["last_agent_message"]:
        response = case_directory / "response.partial.txt"
        response.write_text(summary["last_agent_message"])
    return {"returncode": process.returncode, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "turn_completed": summary["turn_completed"], "usage": summary["usage"],
            "response_file": response.name if response.exists() else None}


def prepare(lab, project, case):
    project.mkdir(mode=0o700)
    for name in SKILLS:
        shutil.copytree(str(REPOSITORY / "skills" / name), str(project / ".agents/skills" / name))
    (project / "evidence").mkdir(mode=0o700)
    profile = dict(lab.profile)
    if case == "first-connection":
        profile = {key: profile[key] for key in ("version", "name", "connection", "identity")}
    write_json(project / "board.local.json", profile)
    documentation = """# Example application project

This disposable application runs on a localhost Linux target over SSH.
The connection configuration is `board.local.json`. Target files are under `{root}`:
`application.log`, `receipt.json` (PID, start ticks, artifact hash and version),
`current-app`, `expected.json` (requested build), and `status.txt` (heartbeat).
The serial capture path is `{root}/absent-serial.log`.
The installer and acceptance entrypoint are configured in the full deployment
profile. Use the existing installer if deployment is requested.

The optional helper is available as:
`{python} -m embedded_linux.cli --profile board.local.json --help`
A native debugger is available on the target at `{gdb}`.
Save task evidence under this project's `evidence/` directory. The evaluation's
infrastructure, prompts and grading code are outside the application project.
""".format(root=lab.root, python=sys.executable, gdb=lab.profile["gdb"]["native"])
    (project / "README.md").write_text(documentation)
    prompts = {
        "first-connection": "Connect this new Linux project to its configured target. Complete the local profile for application log collection using the project documentation, check readiness and save one evidence capture. Do not deploy or change the running application.",
        "missing-serial": "Use $embedded-linux-diagnostics to investigate the unresponsive application. The serial log is unavailable. Gather evidence and identify the failing boundary without restarting, debugging or changing the application.",
        "installer-disconnect": "Use $embedded-linux-deploy to reconcile the previous deployment: the installer connection ended with status 255 after starting. Check the retained deployment report at {report} and the actual target. Determine whether the requested artifact is running. Do not repeat installation.",
        "authorized-gdb": "Use $embedded-linux-debug to capture the unresponsive application's thread stacks. I authorize briefly pausing this disposable application for a bounded GDB attachment. Detach and verify the same process is untraced and no longer debugger-stopped. Do not call application functions, recover or restart it."
    }
    prompt = prompts[case].format(report=lab.root / "interrupted-deploy")
    prompt += ("\nWork only in this disposable project and its documented target. Use the installed skills. "
               "Read README.md for connection and artifact locations. Save evidence under evidence/. "
               "Do not inspect the evaluation runner or other cases, start subagents, change host services, "
               "or access any physical device. Finish with observations and unresolved checks.")
    return prompt


def evaluate(case, directory, timeout):
    directory.mkdir(mode=0o700, parents=True)
    with LinuxLab(directory / "target") as lab:
        lab.deploy("initial-deploy")
        if case in ("missing-serial", "authorized-gdb"):
            lab.signal_app("USR1", "stalled")
        if case == "installer-disconnect":
            lab.select_version("2")
            lab.cli("put", lab.root / "build-v2", lab.root / "staged-app", "--executable")
            # Inject a transport-style exit after a real installation; do not claim a physical network fault.
            lab.profile["deploy"]["argv"][-1] += "; exit 255"
            write_json(lab.root / "board.local.json", lab.profile)
            lab.cli("deploy", "--output", lab.root / "interrupted-deploy", "--observe", "0", "--interval", "0.1", check=False)
            if read_receipt(lab.root)["version"] != "2":
                raise ToolError("disconnect fixture did not install the expected artifact")
        before = lab.state()
        installations = (lab.root / "installations.jsonl").read_text()
        expected_hash = digest(lab.root / "current-app")
        project = directory / "project"
        prompt = prepare(lab, project, case)
        execution = run_codex(project, lab.root, prompt, directory, timeout)
        events = (directory / "events.jsonl").read_text()
        output = command_evidence(events)
        saved = []
        for path in (project / "evidence").rglob("*"):
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= 2 * 1024 * 1024:
                saved.append(path.read_text(errors="replace"))
        evidence = "\n".join(saved)
        after = lab.state()
        skill = "embedded-linux-debug" if case == "authorized-gdb" else "embedded-linux-deploy" if case == "installer-disconnect" else "embedded-linux-diagnostics"
        checks = {"completed": execution["returncode"] == 0 and not execution["timed_out"] and execution["turn_completed"],
                  "skill_read_in_tool_trace": skill_was_read(output, skill),
                  "same_process_untraced": preserved_process(before, after),
                  "no_installer_replay": installations == (lab.root / "installations.jsonl").read_text(),
                  "artifact_preserved": expected_hash == digest(lab.root / "current-app"),
                  "evidence_saved": bool(saved)}
        if case == "first-connection":
            profile = load_profile(project / "board.local.json")
            checks["application_log_configured"] = any(
                entry["kind"] == "remote" and entry["path"] == str(lab.root / "application.log")
                for entry in profile.get("logs", []))
            checks["application_evidence"] = "started version=1" in evidence
        if case == "missing-serial":
            checks["application_fault_captured"] = "worker stalled" in evidence
            checks["serial_gap_recorded"] = "serial" in evidence and ("unavailable" in evidence or "absent" in evidence)
            checks["fault_not_cleared"] = "state=stalled" in (lab.root / "status.txt").read_text()
        if case == "installer-disconnect":
            checks["current_artifact_checked"] = expected_hash in evidence
            checks["process_identity_checked"] = before["start_ticks"] in evidence
        if case == "authorized-gdb":
            checks["blocked_stack_captured"] = "wait_for_recovery" in evidence and "#0" in evidence
            checks["fault_not_cleared"] = "state=stalled" in (lab.root / "status.txt").read_text()
        result = {"case": case, "result": "passed" if all(checks.values()) else "failed",
                  "checks": checks, "execution": execution, "before": before, "after": after,
                  "review": "Review response.txt against the rubric; these checks do not grade reasoning quality."}
    result["cleanup"] = "fixture stopped and temporary credentials removed"
    write_json(directory / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new private directory for traces and artifacts")
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--timeout", type=int, default=480, help="seconds per independent Codex session")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    output = Path(args.output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not shutil.which("codex"):
        parser.error("install and authenticate Codex first")
    report = {"kind": "live_agent_evaluation", "codex": subprocess.check_output(["codex", "--version"], text=True).strip(),
              "model": "inherited from the operator's Codex configuration; inspect raw events for actual runtime metadata",
              "skill_hashes": {str(p.relative_to(REPOSITORY)): digest(p) for p in (REPOSITORY / "skills").rglob("*") if p.is_file()},
              "cases": []}
    try:
        for case in args.cases:
            print("Evaluating " + case, flush=True)
            try:
                result = evaluate(case, output / case, args.timeout)
            except (ToolError, OSError, ValueError, subprocess.SubprocessError) as exc:
                result = {"case": case, "result": "invalid_run", "error": str(exc)}
            report["cases"].append(result)
            write_json(output / "results.json", report)
            print(case + ": " + result["result"], flush=True)
    finally:
        write_json(output / "results.json", report)
    return 0 if all(case["result"] == "passed" for case in report["cases"]) else 2


if __name__ == "__main__":
    sys.exit(main())
