import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("skill_eval", Path(__file__).parents[1] / "evals/run.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


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
