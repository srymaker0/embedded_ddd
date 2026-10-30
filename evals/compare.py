#!/usr/bin/env python3
"""Prepare build/test comparisons without a model; explicitly run them with Codex."""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_cases import CASES, FIXTURE, PROMPTS, digest, grade, prepare_fixture, snapshot
from run import REPOSITORY, command_evidence, run_codex

DEVICE_SKILLS = ("embedded-linux-deploy", "embedded-linux-diagnostics", "embedded-linux-debug")
VARIANTS = {"no-project-skills": (), "ddd": DEVICE_SKILLS,
            "expanded": DEVICE_SKILLS + ("embedded-linux-build", "embedded-linux-test")}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def skill_hashes(project):
    root = project / ".agents/skills"
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("comparison skills must remain independent copies")
        if path.is_file():
            result[str(path.relative_to(root))] = digest(path)
    return result


def prepare(output, cases, variants):
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    plan = {"kind": "prepared_skill_comparison", "model_sessions_started": 0,
            "fixture_hashes": {str(path.relative_to(FIXTURE)): digest(path)
                               for path in sorted(FIXTURE.rglob("*")) if path.is_file()},
            "cases": [], "limits": [
                "Variants change only project skill copies; global instructions, skills and plugins remain inherited.",
                "One attempt per case and variant is exploratory, not a reliability or significance estimate.",
                "Human review of conclusions and forbidden operations is required alongside automatic checks."]}
    for index, case in enumerate(cases):
        # Rotate the starting condition so a single variant is not always first.
        ordered = variants[index % len(variants):] + variants[:index % len(variants)]
        for variant in ordered:
            relative = case + "/" + variant
            directory = output / relative
            directory.mkdir(parents=True, mode=0o700)
            project = directory / "project"
            before = prepare_fixture(project)
            for skill in VARIANTS[variant]:
                shutil.copytree(str(REPOSITORY / "skills" / skill), str(project / ".agents/skills" / skill))
            prompt = PROMPTS[case] + (
                "\nRead this project's README.md for its commands and facts. Work only inside this "
                "temporary project. Do not inspect sibling projects or evaluation infrastructure, "
                "start independent agents, or access external services. Save any verification "
                "evidence under evidence/ and finish with the result and its limits.")
            (directory / "prompt.txt").write_text(prompt)
            write_json(directory / "before.json", before)
            plan["cases"].append({"case": case, "variant": variant, "directory": relative,
                                  "skills": list(VARIANTS[variant]), "skill_hashes": skill_hashes(project),
                                  "prompt_sha256": digest(directory / "prompt.txt"),
                                  "before_sha256": digest(directory / "before.json")})
    write_json(output / "plan.json", plan)
    return plan


def environment_fingerprint():
    """Record context fingerprints, never credentials or configuration contents."""
    codex_directory = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    roots = (codex_directory / "skills", Path.home() / ".agents/skills", Path("/etc/codex/skills"))
    skills = {}
    for root in roots:
        for path in sorted(root.rglob("SKILL.md")) if root.is_dir() else ():
            skills[str(path)] = digest(path)
    files = (codex_directory / "config.toml", codex_directory / "AGENTS.md", codex_directory / "AGENTS.override.md")
    return {"user_file_hashes": {str(path): digest(path) for path in files if path.is_file()},
            "global_skill_entrypoint_hashes": skills,
            "limitations": "Plugin state and remote settings are not fully fingerprinted. Review tool traces for outside skills."}


def trace_observations(events):
    output = command_evidence(events)
    loaded = []
    for name in VARIANTS["expanded"]:
        if "name: " + name + "\n" in output and "# Embedded Linux" in output:
            loaded.append(name)
    commands = []
    for line in events.splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands.append(item.get("command", ""))
    # This is a review aid, not a complete shell interpreter or a network audit.
    flagged = [command for command in commands if prohibited_execution(command)]
    return {"project_skills_visible_in_successful_output": loaded,
            "commands_requiring_review_for_explanation_only": flagged,
            "command_count": len(commands)}


def prohibited_execution(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return False  # Unknown syntax remains a manual review item.
    groups = [[]]
    for token in tokens:
        if token and all(character in ";&|()\n" for character in token):
            groups.append([])
        else:
            groups[-1].append(token)
    for argv in groups:
        while argv and "=" in argv[0] and not argv[0].startswith("/"):
            argv = argv[1:]
        if not argv:
            continue
        executable = Path(argv[0]).name
        if executable in ("sh", "bash", "dash", "zsh"):
            for index, arg in enumerate(argv[1:], 1):
                if arg.startswith("-") and "c" in arg and index + 1 < len(argv):
                    if prohibited_execution(argv[index + 1]):
                        return True
        if executable in {"ssh", "scp", "sftp", "telnet", "gdb", "gdbserver", "gcc", "cc", "make", "cmake", "ninja"}:
            return True
        if (executable.startswith("python") and len(argv) > 2 and Path(argv[1]).name == "project.py"
                and argv[2] in ("build", "stage", "package", "test")):
            return True
        if executable == "project.py" and len(argv) > 1 and argv[1] in ("build", "stage", "package", "test"):
            return True
    return False


def validate_plan(output, plan):
    if plan.get("kind") != "prepared_skill_comparison" or not plan.get("cases"):
        raise ValueError("not a prepared comparison plan")
    for item in plan["cases"]:
        if item["case"] not in CASES or item["variant"] not in VARIANTS:
            raise ValueError("unknown comparison case or variant")
        if item["directory"] != item["case"] + "/" + item["variant"]:
            raise ValueError("invalid case directory")
        directory = output / item["directory"]
        if (directory / "events.jsonl").exists() or (directory / "result.json").exists():
            raise ValueError("plan already attempted; prepare a new directory to avoid overwriting evidence")
        before = json.loads((directory / "before.json").read_text())
        if (digest(directory / "prompt.txt") != item["prompt_sha256"]
                or digest(directory / "before.json") != item["before_sha256"]
                or snapshot(directory / "project") != before
                or skill_hashes(directory / "project") != item["skill_hashes"]):
            raise ValueError("prepared case has changed: " + item["directory"])


def run(output, timeout):
    plan = json.loads((output / "plan.json").read_text())
    validate_plan(output, plan)
    if not shutil.which("codex"):
        raise RuntimeError("install and authenticate Codex before running a comparison")
    report = {"kind": "live_skill_comparison", "plan_sha256": digest(output / "plan.json"),
              "runner_hashes": {name: digest(Path(__file__).parent / name)
                                for name in ("compare.py", "build_cases.py", "run.py")},
              "codex": subprocess.check_output(["codex", "--version"], text=True, timeout=10).strip(),
              "model": "inherited operator model and reasoning configuration; no override",
              "environment": environment_fingerprint(), "limits": plan["limits"], "cases": []}
    try:
        for item in plan["cases"]:
            directory = output / item["directory"]
            project = directory / "project"
            result = {"case": item["case"], "variant": item["variant"], "review": "pending"}
            print("Evaluating " + item["directory"], flush=True)
            try:
                before = json.loads((directory / "before.json").read_text())
                execution = run_codex(project, None, (directory / "prompt.txt").read_text(), directory,
                                      timeout, network=False)
                result["execution"] = execution
                observations = trace_observations((directory / "events.jsonl").read_text())
                result["trace"] = observations
                result.update(grade(item["case"], project, before, directory / "grading"))
                result["checks"]["installed_skills_preserved"] = skill_hashes(project) == item["skill_hashes"]
                result["checks"]["session_completed"] = (execution["returncode"] == 0
                    and not execution["timed_out"] and execution["turn_completed"])
                if item["case"] == "explain-build-commands":
                    result["checks"]["no_flagged_execution"] = not observations["commands_requiring_review_for_explanation_only"]
                result["result"] = "passed" if all(result["checks"].values()) else "failed"
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, tarfile.TarError) as exc:
                result.update(result="invalid_run", error=str(exc))
            write_json(directory / "result.json", result)
            report["cases"].append(result)
            write_json(output / "results.json", report)
            print(item["directory"] + ": " + result["result"], flush=True)
    finally:
        report["environment_unchanged"] = report["environment"] == environment_fingerprint()
        write_json(output / "results.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare", help="compile fixtures and copy skills; no model calls")
    prepare_command.add_argument("--output", required=True, help="new private directory, preferably under /tmp")
    prepare_command.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    prepare_command.add_argument("--variants", nargs="+", choices=tuple(VARIANTS), default=list(VARIANTS))
    run_command = commands.add_parser("run", help="start one paid Codex session per prepared case and variant")
    run_command.add_argument("--input", required=True, help="directory produced by prepare")
    run_command.add_argument("--timeout", type=int, default=480, help="maximum seconds per model session")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            if len(set(args.cases)) != len(args.cases) or len(set(args.variants)) != len(args.variants):
                parser.error("cases and variants must not contain duplicates")
            output = Path(args.output).resolve()
            plan = prepare(output, args.cases, args.variants)
            print("Prepared {} cases; no model sessions started. Plan: {}".format(len(plan["cases"]), output / "plan.json"))
            return 0
        if args.timeout <= 0:
            parser.error("--timeout must be positive")
        report = run(Path(args.input).resolve(), args.timeout)
        return 0 if report["environment_unchanged"] and all(case["result"] == "passed" for case in report["cases"]) else 2
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    sys.exit(main())
