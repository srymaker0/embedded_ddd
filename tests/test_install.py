import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.link_skills import install_skills


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("embedded-linux-deploy", "embedded-linux-diagnostics", "embedded-linux-debug")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def assert_installed(self, destination, targets):
        self.assertEqual(set(targets), {destination / name for name in SKILLS})
        for target in targets:
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), ROOT / "skills" / target.name)
            self.assertTrue((target / "SKILL.md").is_file())

    def test_user_install_for_both_clients_is_repeatable_and_preserves_other_skills(self):
        with patch("scripts.link_skills.Path.home", return_value=self.root), patch.dict(os.environ):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            for agent, folder in (("codex", ".agents"), ("claude", ".claude")):
                with self.subTest(agent=agent):
                    destination = self.root / folder / "skills"
                    other = destination / "my-existing-skill" / "SKILL.md"
                    other.parent.mkdir(parents=True)
                    other.write_text("keep this skill")
                    targets = install_skills(agent)
                    self.assert_installed(destination, targets)
                    before = {path: path.lstat().st_ino for path in targets}
                    self.assertEqual(install_skills(agent), targets)
                    self.assertEqual(before, {path: path.lstat().st_ino for path in targets})
                    self.assertEqual(other.read_text(), "keep this skill")

    def test_claude_config_directory_applies_only_to_user_install(self):
        config = self.root / "custom claude"
        project = self.root / "project"
        project.mkdir()
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}):
            self.assert_installed(config / "skills", install_skills("claude"))
            self.assert_installed(project / ".claude/skills", install_skills("claude", project))

    def test_conflicting_directory_or_dangling_link_does_not_partially_install(self):
        for agent, folder in (("codex", ".agents"), ("claude", ".claude")):
            for kind in ("directory", "dangling-link"):
                with self.subTest(agent=agent, kind=kind):
                    project = self.root / agent / kind
                    destination = project / folder / "skills"
                    destination.mkdir(parents=True)
                    conflict = destination / sorted(SKILLS)[-1]
                    if kind == "directory":
                        conflict.mkdir()
                        (conflict / "SKILL.md").write_text("user skill")
                    else:
                        conflict.symlink_to(self.root / "missing-source")
                    with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                        install_skills(agent, project)
                    self.assertEqual(list(destination.iterdir()), [conflict])
                    if kind == "directory":
                        self.assertEqual((conflict / "SKILL.md").read_text(), "user skill")
                    else:
                        self.assertEqual(Path(os.readlink(conflict)), self.root / "missing-source")

    def test_project_cli_registers_both_clients_and_excludes_only_its_own_links(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        exclude = self.root / ".git/info/exclude"
        exclude.write_text("# keep existing rules\nprivate.local")
        # A project may be a subdirectory of a larger Git repository.
        project = self.root / "nested project"
        project.mkdir()
        for agent, folder in (("codex", ".agents"), ("claude", ".claude")):
            with self.subTest(agent=agent):
                command = [sys.executable, str(ROOT / "scripts/link_skills.py"), "--agent", agent,
                           "--project", str(project), "--git-exclude"]
                result = subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)
                targets = [Path(line) for line in result.stdout.splitlines()]
                self.assert_installed(project / folder / "skills", targets)
                before = exclude.read_text()
                subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)
                self.assertEqual(exclude.read_text(), before)
                for target in targets:
                    subprocess.run(["git", "-C", str(self.root), "check-ignore", "-q", str(target)], check=True)
                unrelated = project / folder / "skills/unrelated"
                unrelated.mkdir()
                self.assertEqual(subprocess.run(["git", "-C", str(self.root), "check-ignore", "-q",
                                                 str(unrelated)]).returncode, 1)
        self.assertTrue(exclude.read_text().startswith("# keep existing rules\nprivate.local\n"))
        self.assertEqual(len(exclude.read_text().splitlines()), 2 + 2 * len(SKILLS))

    def test_git_exclude_requires_a_project_before_user_files_are_created(self):
        with patch("scripts.link_skills.Path.home", return_value=self.root):
            with self.assertRaisesRegex(ValueError, "requires --project"):
                install_skills("codex", git_exclude=True)
        self.assertEqual(list(self.root.iterdir()), [])
