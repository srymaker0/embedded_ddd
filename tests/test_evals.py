import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("skill_eval", Path(__file__).parents[1] / "evals/run.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)

spec = importlib.util.spec_from_file_location("skill_compare", Path(__file__).parents[1] / "evals/compare.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
from build_cases import OLD_SENSOR, command, grade, prepare_fixture, snapshot


class EvaluationGradingTests(unittest.TestCase):
    def test_final_claim_or_failed_read_does_not_count_as_skill_use(self):
        text = "name: embedded-linux-debug\n# Embedded Linux Debug"
        events = [
            {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
            {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1,
                                                "aggregated_output": text}}]
        output = evaluation.command_evidence("\n".join(map(json.dumps, events)))
        self.assertFalse(evaluation.skill_was_read(output, "embedded-linux-debug"))
        events.append({"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
                                                          "aggregated_output": text}})
        output = evaluation.command_evidence("\n".join(map(json.dumps, events)))
        self.assertTrue(evaluation.skill_was_read(output, "embedded-linux-debug"))

    def test_pid_reuse_stopped_and_traced_processes_fail_recovery(self):
        before = {"pid": 42, "start_ticks": "123", "state": "S", "tracer_pid": 0}
        self.assertTrue(evaluation.preserved_process(before, dict(before)))
        for change in ({"start_ticks": "124"}, {"pid": 43}, {"state": "T"}, {"tracer_pid": 7}):
            self.assertFalse(evaluation.preserved_process(before, {**before, **change}))

    def test_last_answer_without_turn_completion_is_incomplete(self):
        message = {"type": "item.completed", "item": {"type": "agent_message", "text": "Done"}}
        summary = evaluation.trace_summary(json.dumps(message))
        self.assertFalse(summary["turn_completed"])
        self.assertEqual(summary["last_agent_message"], "Done")
        completed = {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}}
        summary = evaluation.trace_summary(json.dumps(message) + "\n" + json.dumps(completed))
        self.assertTrue(summary["turn_completed"])
        self.assertEqual(summary["usage"], completed["usage"])


@unittest.skipUnless(shutil.which("gcc"), "build/test evaluation fixtures require GCC")
class BuildComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory()
        cls.template = Path(cls.fixture_directory.name) / "template"
        prepare_fixture(cls.template)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        shutil.copytree(str(self.template), str(self.project))
        self.before = snapshot(self.project)

    def grade(self, case, name="grading"):
        return grade(case, self.project, self.before, self.root / name)

    def action(self, action):
        result = command(self.project, sys.executable, "project.py", action)
        self.assertEqual(result.returncode, 0, result.stdout)

    def correct_package_input(self):
        path = self.project / "package.json"
        config = json.loads(path.read_text())
        config["library"] = "stage/lib/libsample.so"
        path.write_text(json.dumps(config))

    def add_regression(self, contents):
        (self.project / "tests/test_sensor.c").write_text(contents)
        path = self.project / "tests/suite.json"
        suite = json.loads(path.read_text())
        suite["sensor"] = ["tests/test_sensor.c", "src/sensor.c"]
        path.write_text(json.dumps(suite))

    def test_stale_package_fails_despite_updated_build_and_staging(self):
        result = self.grade("build-artifact-provenance")
        self.assertFalse(result["checks"]["final_package_contains_fix"])
        self.assertFalse(result["checks"]["recipe_reproduces_fix"])
        self.correct_package_input()
        self.action("package")
        result = self.grade("build-artifact-provenance", "corrected")
        self.assertTrue(all(result["checks"].values()), result)

    def test_manually_replaced_archive_does_not_prove_recipe_fixed(self):
        original = (self.project / "package.json").read_bytes()
        self.correct_package_input()
        self.action("package")
        (self.project / "package.json").write_bytes(original)
        result = self.grade("build-artifact-provenance")
        self.assertTrue(result["checks"]["final_package_contains_fix"])
        self.assertFalse(result["checks"]["recipe_reproduces_fix"])

    def test_stub_pass_is_not_coverage_and_real_regression_rejects_old_code(self):
        initial = self.grade("test-replaced-dependency")
        self.assertTrue(initial["checks"]["current_implementation_passes"])
        self.assertFalse(initial["checks"]["regression_rejects_old_implementation"])
        self.add_regression('#include <assert.h>\n#include "sensor.h"\n'
                            'int main(void) { assert(sensor_decode(0xfff) == -1); return 0; }\n')
        result = self.grade("test-replaced-dependency", "regression")
        self.assertTrue(all(result["checks"].values()), result)

    def test_empty_and_always_passing_suites_do_not_verify_fix(self):
        self.add_regression("int main(void) { return 0; }\n")
        result = self.grade("test-replaced-dependency")
        self.assertFalse(result["checks"]["regression_rejects_old_implementation"])
        (self.project / "tests/suite.json").write_text("{}")
        result = self.grade("test-replaced-dependency", "empty")
        self.assertFalse(result["checks"]["current_implementation_passes"])
        self.assertFalse(result["checks"]["regression_rejects_old_implementation"])

    def test_compile_error_is_not_a_successful_regression_detection(self):
        self.add_regression("int main(void) { return missing_symbol; }\n")
        result = self.grade("test-replaced-dependency")
        self.assertFalse(result["checks"]["current_implementation_passes"])
        self.assertFalse(result["checks"]["old_implementation_compiles"])
        self.assertFalse(result["checks"]["regression_rejects_old_implementation"])

    def test_explanation_must_preserve_files_and_not_execute_build(self):
        self.assertTrue(all(self.grade("explain-build-commands")["checks"].values()))
        self.action("build")
        result = self.grade("explain-build-commands")
        self.assertFalse(result["checks"]["project_unchanged"])
        self.assertFalse(result["checks"]["no_project_actions"])

    def test_reverting_production_fix_fails_even_if_tests_pass(self):
        (self.project / "src/sensor.c").write_text(OLD_SENSOR)
        result = self.grade("test-replaced-dependency")
        self.assertFalse(result["checks"]["production_sources_preserved"])

    def test_prepare_installs_independent_variants_without_model_calls(self):
        output = self.root / "comparison"
        with mock.patch.object(comparison, "run_codex", side_effect=AssertionError("unexpected model call")):
            plan = comparison.prepare(output, ["explain-build-commands"], list(comparison.VARIANTS))
        self.assertEqual(plan["model_sessions_started"], 0)
        prompts = set()
        files = []
        for item in plan["cases"]:
            directory = output / item["directory"]
            project = directory / "project"
            installed = {path.parent.name for path in (project / ".agents/skills").glob("*/SKILL.md")}
            self.assertEqual(installed, set(comparison.VARIANTS[item["variant"]]))
            self.assertFalse(any(path.is_symlink() for path in project.rglob("*")))
            prompts.add((directory / "prompt.txt").read_text())
            files.append({name: value["sha256"] for name, value in snapshot(project).items()})
        self.assertEqual(len(prompts), 1)
        self.assertTrue(all(files[0] == contents for contents in files))
        comparison.validate_plan(output, plan)
        (output / plan["cases"][0]["directory"] / "prompt.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "prepared case has changed"):
            comparison.validate_plan(output, plan)

    def test_completed_baseline_needs_no_skill_read_and_cannot_be_replayed(self):
        output = self.root / "comparison"
        comparison.prepare(output, ["explain-build-commands"], ["no-project-skills"])

        def recorded_session(project, target, prompt, directory, timeout, network):
            self.assertIsNone(target)
            self.assertFalse(network)
            event = {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}
            (directory / "events.jsonl").write_text(json.dumps(event) + "\n")
            (directory / "response.txt").write_text("Simulated response for runner regression testing.")
            return {"returncode": 0, "timed_out": False, "turn_completed": True,
                    "usage": event["usage"], "elapsed_seconds": 0, "response_file": "response.txt"}

        with mock.patch.object(comparison, "run_codex", side_effect=recorded_session) as session, \
                mock.patch.object(comparison.shutil, "which", return_value="codex"), \
                mock.patch.object(comparison.subprocess, "check_output", return_value="codex test fixture"), \
                mock.patch.object(comparison, "environment_fingerprint", return_value={}):
            report = comparison.run(output, 10)
            session.assert_called_once()
            self.assertEqual(report["cases"][0]["result"], "passed")
            self.assertEqual(report["cases"][0]["review"], "pending")
            self.assertEqual(report["cases"][0]["trace"]["project_skills_visible_in_successful_output"], [])
            self.assertTrue(report["environment_unchanged"])
            with self.assertRaisesRegex(ValueError, "already attempted"):
                comparison.run(output, 10)


class ComparisonTraceTests(unittest.TestCase):
    def test_command_mentions_are_distinct_from_execution(self):
        for text in ("rg -n gcc README.md", "cat project.py", "python3 project.py --help",
                     "bash -lc 'sed -n 1,40p README.md'"):
            self.assertFalse(comparison.prohibited_execution(text), text)
        for text in ("gcc src/main.c", "python3 project.py build", "./project.py package",
                     "bash -lc 'cd /tmp/example && python3 project.py test'", "cat README.md\nssh localhost"):
            self.assertTrue(comparison.prohibited_execution(text), text)
