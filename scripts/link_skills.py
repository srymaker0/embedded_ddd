#!/usr/bin/env python3
"""Install this checkout's skills for Codex or Claude Code using symbolic links."""

import argparse
import os
import subprocess
from pathlib import Path


def skill_directory(agent, project=None):
    if project is not None:
        return project / (".agents" if agent == "codex" else ".claude") / "skills"
    if agent == "claude":
        config = os.environ.get("CLAUDE_CONFIG_DIR")
        return (Path(config).expanduser() if config else Path.home() / ".claude") / "skills"
    return Path.home() / ".agents" / "skills"


def install_skills(agent, project=None, git_exclude=False):
    if git_exclude and project is None:
        raise ValueError("--git-exclude requires --project")
    if project is not None:
        project = project.expanduser().resolve(strict=True)
        if not project.is_dir():
            raise ValueError("project is not a directory: " + str(project))
    source = Path(__file__).resolve().parents[1] / "skills"
    sources = sorted(path for path in source.iterdir() if (path / "SKILL.md").is_file())
    if not sources:
        raise ValueError("no skills found in " + str(source))
    destination = skill_directory(agent, project)
    targets = [destination / path.name for path in sources]
    # Check all names before creating links so a conflict cannot leave a partial install.
    for path in sources:
        target = destination / path.name
        if (target.exists() or target.is_symlink()) and target.resolve() != path.resolve():
            raise FileExistsError("refusing to overwrite existing skill: " + str(target))

    exclude = None
    missing = []
    existing = ""
    if git_exclude:
        root_result = subprocess.run(["git", "-C", str(project), "rev-parse", "--show-toplevel"],
                                     check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        git_root = Path(root_result.stdout.strip()).resolve()
        result = subprocess.run(["git", "-C", str(project), "rev-parse", "--git-path", "info/exclude"],
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        exclude = Path(result.stdout.strip())
        if not exclude.is_absolute():
            exclude = project / exclude
        existing = exclude.read_text() if exclude.exists() else ""
        entries = ["/" + target.relative_to(git_root).as_posix() for target in targets]
        missing = [entry for entry in entries if entry not in existing.splitlines()]

    destination.mkdir(parents=True, exist_ok=True)
    for path, target in zip(sources, targets):
        if not target.is_symlink():
            target.symlink_to(path, target_is_directory=True)
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as stream:
            stream.write(("\n" if existing and not existing.endswith("\n") else "") + "\n".join(missing) + "\n")
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("codex", "claude"), default="codex",
                        help="client to install for (default: codex)")
    parser.add_argument("--project", type=Path,
                        help="install only for this project instead of the current user")
    parser.add_argument("--git-exclude", action="store_true",
                        help="ignore only these links in the project's local Git excludes")
    args = parser.parse_args()
    try:
        targets = install_skills(args.agent, args.project, args.git_exclude)
    except subprocess.CalledProcessError as error:
        parser.exit(1, "error: " + error.stderr.strip() + "\n")
    except (OSError, ValueError) as error:
        parser.exit(1, "error: " + str(error) + "\n")
    for target in targets:
        print(target)


if __name__ == "__main__":
    main()
