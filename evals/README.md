# Live skill evaluations

These evaluations launch independent Codex sessions with real tools against the
[disposable Linux lab](../examples/README.md). They check behavior beyond a scenario
checklist or a model's own claim that it followed a skill.

The [recorded run from 2026-10-29](results/2026-10-29.json) has three passing cases
and one timeout. First-connection behavior checks passed, but that session did not
emit its completion event before 480 seconds, so its overall result remains failed.
The report includes skill hashes, individual checks, available token usage and limits.

Prepare the lab dependencies and authenticate the installed Codex CLI, then run:

```sh
.venv/bin/python evals/run.py --output output/evals-001
```

This command explicitly starts four model sessions in sequence and consumes your
model quota. It inherits your configured Codex model and reasoning settings. It
does not automatically reduce them or run in CI. Each session has a 480-second
deadline; select cases with `--cases missing-serial authorized-gdb`, or change the
deadline with `--timeout 900`. When an assistant runs this on your behalf, any local
requirement to authorize independent agents still applies.

Each case gets a fresh project containing copies of the current source skills,
connection facts, an evidence directory and one target application. A workspace
sandbox permits writes to that project/target and network access for localhost SSH.
SSH provides access as the development user, not a separate OS sandbox; the prompts
restrict the sessions to the disposable target. Use a dedicated development VM for
evaluating untrusted skill changes. The runner never switches to an unrestricted
sandbox if the configured sandbox fails.

| Case | Request | Observable checks |
| --- | --- | --- |
| `first-connection` | Complete a minimal profile and collect application evidence | Diagnostics skill read, log configuration and evidence, unchanged application |
| `missing-serial` | Investigate an unresponsive application without serial evidence | Application fault captured, serial gap recorded, no restart or fault clearing |
| `installer-disconnect` | Reconcile a deployment whose connection ended with status 255 | Current artifact and process evidence, no repeated installer invocation |
| `authorized-gdb` | Capture stacks with an already authorized pause | Blocked function in stacks, same process untraced afterward, no recovery or restart |

The disconnect fixture performs a real installation, then deliberately returns
status 255. It evaluates reconciliation of an ambiguous result; it does not simulate
every possible network timing or interruption inside a flash write.

## Read the results

`results.json` records the Codex version, source skill hashes and each outcome.
Each case retains its exact prompt, raw JSONL tool events, stderr, final response,
evidence, before/after process state and individual checks. Raw runs are private by
default and excluded when placed under the repository's `output/` directory.
Review them for local paths and device information before sharing.

The checks require successful tool output containing the loaded skill, saved
evidence, and actual target invariants. A final answer claiming success is not
enough. Completion also requires a `turn.completed` event and a normal exit before
the deadline. A failed check is `failed`; fixture/setup or incompatible trace errors are
`invalid_run`. The command exits nonzero for either. Timeouts remain explicit.

Inspect `response.txt` alongside the original evidence to grade explanation quality,
unsupported conclusions and unresolved acceptance. Automated checks do not establish
that every sentence is correct, nor do four cases establish reliability on arbitrary
hardware. If the CLI did not save a final response, `response.partial.txt` preserves
its last available message without treating that message as proof of completion.
Usage is recorded when the CLI emits it; a missing usage event does not mean the run
consumed no tokens. The [scenario rubric](scenarios.json) also lists transfer selection, log
overwrite, constrained memory, offline cores and simulated callback cases that need
separate evaluation. No run is counted as passed merely because its prompt exists.
