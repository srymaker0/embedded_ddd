# Live skill evaluations

The embedded-skills collection has both build/test skills and a DDD device workflow.
Two runners exercise different parts of the collection:

- `run.py` evaluates four device scenarios against the
  [disposable Linux lab](../examples/README.md).
- `compare.py` prepares three build/test scenarios and compares no project skills,
  the three DDD skills, and the five-skill collection. Preparation does not call a
  model; running the default comparison starts nine independent Codex sessions.

Both use actual tools and observable outcomes. Passing the helper's host tests or
the fixture's grading tests does not establish skill behavior.

The [recorded run from 2026-10-29](results/2026-10-29.json) has three passing cases
and one timeout. First-connection behavior checks passed, but that session did not
emit its completion event before 480 seconds, so its overall result remains failed.
The report includes skill hashes, individual checks, available token usage and limits.
It predates the build and test skills and applies to the recorded revision of the
three device skills, not to later changes or the expanded collection.

## Build and test comparison

Use Linux, Python 3.8+ and native GCC, with the development environment installed
as described in the main README. This fixture needs no SSH server, GDB or board.
Prepare the inputs without starting Codex:

```sh
.venv/bin/python evals/compare.py prepare --output /tmp/embedded-skills-comparison-001
```

This creates nine independent projects and a `plan.json`, with exact prompts,
source hashes, installed skill hashes and initial file snapshots. Use a fresh
directory outside your application checkout so its project instructions and skills
do not enter the comparison. `--cases build-artifact-provenance` or
`--variants no-project-skills expanded` prepares a smaller comparison.

| Scenario | Initial condition | Automatic outcome checks |
| --- | --- | --- |
| `build-artifact-provenance` | Source and staging contain the signed-value fix; the package recipe selects an old vendor library | Inspect the delivered library, execute native boundary cases, rebuild in a separate copy and verify the recipe reproduces the fix |
| `test-replaced-dependency` | Existing host test passes using a sensor stub | Recompile registered tests independently; current production code must pass and substituting the old implementation must cause a test failure, not a compile failure |
| `explain-build-commands` | User asks only what build, stage and package do | Source, configuration and artifact files retain their contents and timestamps, no project action is recorded, tool trace has no detected build or device command |

The [sample project](fixtures/build-project/README.md) is a native Linux fixture
with an existing build entrypoint, package configuration and C test suite. It checks
package provenance and test coverage boundaries, not cross-compilation, peripheral
timing or real hardware acceptance. Production sources must be preserved in every
case. The grading tests also reject empty and always-passing test suites, and an
archive replaced by hand while the package recipe remains wrong.

The three variants receive identical natural-language requests and byte-identical
project inputs. The prompts do not name a skill or require one to be read. Only
project skill copies differ; session order rotates across scenarios. Skill reads
visible in successful tool output are recorded as observations, not pass criteria.
The common prompt permits writing evidence under `evidence/`, including for the
explanation task. These files are excluded from the unchanged-project check;
installed skill files are checked separately. This evaluates execution boundaries,
not a zero-write session.

To execute a prepared comparison after reviewing its scope:

```sh
.venv/bin/python evals/compare.py run --input /tmp/embedded-skills-comparison-001
```

**This starts up to nine model sessions and consumes model quota.** It inherits the
operator's model and reasoning settings, runs sequentially, and defaults to 480
seconds per session (`--timeout 900` changes that limit). Independent-session
authorization requirements in your environment still apply. The runner refuses to
reuse an attempted plan or run projects changed since preparation. CI runs only
the deterministic fixtures and grader tests; it never invokes this command.

`no-project-skills` means no skills from this repository are installed in the
temporary project. User-wide skills, instructions and plugins can still be inherited.
Configuration and global skill entrypoint hashes are recorded without their contents;
plugin state is not fully captured. The workspace sandbox disables shell network
access, but is not a separate operating-system account or a guarantee that external
connector tools are absent. For a strict isolated comparison, use a dedicated
development environment with a fixed model configuration and reviewed skills/plugins.
The runner does not change the operator's global setup.

Each result includes checks, independently rebuilt artifacts or test runs, raw
tool events, final answer, elapsed time and token usage when emitted. Compare
correct outcomes and unintended actions first, then time and usage for successful
runs. One attempt per cell cannot establish statistical reliability. Read the final
answers for coverage claims and command explanations: file invariants and a command
scanner cannot prove every conclusion or detect arbitrary indirect execution.
Command flags are conservative review leads, not proof that a command changed state.
Human review remains `pending` even when all automatic checks pass. A missing usage
event means usage is unknown, not zero.

### Recorded comparison

The [2026-10-29 reviewed run](results/2026-10-29-comparison.json) used Codex 0.163.0
with the operator's `gpt-6-astra` / `max` configuration. It ran each scenario once
under each condition. Native skill discovery confirmed 0, 3 and 5 project skills,
plus the same 23 other skill entries in every project. Configuration and global
skill fingerprints were unchanged through the run.

| Condition | Automatic outcomes | Total session time | Input tokens, including cached | Cached input tokens | Output tokens |
| --- | --- | --- | --- | --- | --- |
| No project skills | 3 / 3 passed | 910.99 s | 704,834 | 612,992 | 20,985 |
| Three DDD skills | 3 / 3 passed | 711.51 s | 628,813 | 561,152 | 17,908 |
| Five skills | 3 / 3 passed | 888.45 s | 803,679 | 716,288 | 21,486 |

The expanded condition naturally loaded Build and Test for packaging, Test for the
regression task, and Build for the explanation task without executing a build.
All variants produced a reproducibly corrected package and tests that reject the
old implementation. All also respected the no-build/no-device boundary for the
explanation task while writing the explicitly permitted evidence file.

Manual review found that every command explanation relied on the README and left
the actual library selection in `package.json` uninspected. The answers qualified
their package guarantees, but the common gap remains visible despite passing
automatic checks. The published record preserves this observation, exact prompts,
source/skill/runner hashes, individual checks and usage. Raw traces and answers
remain local because they contain host paths.

These results establish that the new skills can be selected and followed in these
fixtures. They show no success-rate improvement over the comparison groups, and
one attempt per condition cannot establish an efficiency advantage. Build and Test
remain experimental; further expansion should be driven by real embedded tasks
that expose a repeatable gap, including cross-toolchain and target constraints
not exercised here.

## Device scenarios

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

Each case gets a fresh project containing copies of all current source skills,
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

## Read device results

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
consumed no tokens. These four cases have no baseline comparison, and three prompts
explicitly name their skill; they do not establish automatic skill selection.
The [scenario rubric](scenarios.json) also lists cross-build-only tasks, empty test
selections, transfer selection, log overwrite, constrained memory, offline cores
and simulated callback cases that need separate evaluation. Each entry with
`runner: null` is a manual scenario, not an executed result. A runner being available
does not mean its scenarios have been executed or passed.
