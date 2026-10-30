# Acceptance checks

## What did the test execute?

Trace the test entrypoint to the production implementation and its replaced
dependencies. For example, a host test of retry policy with a stub transport can
verify retry selection; it cannot verify a changed transport implementation that
was not linked into the test. Select another existing check or device scenario
for that changed boundary.

Identify the runner's behavior for empty filters, skipped dependencies and a
build-only target. Preserve those outcomes separately from executed passes.
Coverage percentages and a zero exit status do not identify which requested
scenario ran.

## Device identity and observations

Relate each run to the target hardware, actual installed/running artifact, runtime
configuration and relevant initial state. A retained configuration can differ
from packaged defaults. A reused PID can belong to another process; use boot or
process start identity when correlating logs across restart or deployment.

Follow the observable chain required by the task. A few common distinctions:

| Observation | Additional evidence needed for a broader claim |
| --- | --- |
| A command was accepted | The requested operation reached its completion or failure state |
| A driver wrote to an interface | The peripheral received and performed the operation |
| A mocked event reached application logic | The real external input produced that event |
| An installer returned success | The intended artifact runs and the requested behavior works |
| A network connection is established | The relevant message or transaction was acknowledged at the required endpoint |

Do not collect every possible signal. Pick the ones that distinguish the suspected
failure and establish the requested outcome. Use device-local timestamps for a
single-device interval; reconcile clock offsets before comparing separate clocks.
When latency matters, identify whether the interval ends at acceptance, physical
start or completion.

## Failure, recovery and retained state

For a negative case, define both the failure to provoke and the expected final
state. An update that fails as intended but leaves the application unavailable
has not passed a rollback requirement. Check required data/configuration retention
when the task crosses a restart or upgrade boundary.

Use the project's documented fault injection and recovery mechanisms within the
task's authorization. Do not infer power control, flash safety or watchdog behavior
from a localhost fixture. A connection lost during installation leaves an unknown
outcome until device evidence reconciles it; do not retry the install as a test of
whether the previous one worked.

If hardware, an account or an external operator is unavailable, record the exact
trigger, expected observations and remaining prerequisite. Keep completed host or
emulation evidence and its limits instead of reporting the whole scenario passed.
