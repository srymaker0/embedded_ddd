---
name: embedded-linux-diagnostics
description: Diagnose embedded Linux application failures, crashes, hangs, restarts and abnormal device logs using serial output, SSH or Telnet, application logs, kernel evidence and process identity. Also use to observe a device after deployment or during reproduction.
---

# Embedded Linux diagnostics

Find the failing boundary and the smallest evidence that distinguishes plausible causes. Reuse known target and connection details; ordinary diagnosis starts with read-only evidence.

## Collect evidence automatically

1. Identify the exact target, boot, process start and software artifact. Look for the matching local profile under `~/.config/embedded-linux/` or the project's configured location, and use its SSH/Telnet/serial route and existing project tools. Do not treat the newest file or a matching PID alone as proof of the relevant run.
2. Record the symptom, trigger and expected behavior. If already provided, begin collection without asking for them again.
3. Read available serial evidence and the configured application log. If serial is unavailable, empty during the expected event, overwritten, disconnected or inconclusive, immediately try the application log through the available command connection. If network access fails, retain serial evidence and its continuity limits. An empty log does not establish health.
4. Preserve timestamps, source identity, log boundaries and source failures. Label pre-existing tail content as context. After rotation/truncation, start a new segment and report the gap rather than appending it as if continuous. Application logs may buffer output; correlate process state and other evidence before treating silence as failure.

The optional repository CLI provides bounded multi-source collection:

```sh
embedded-ddd --profile /path/to/board.json collect --output /path/to/new-run --duration 30
```

Resolve the helper from its configured location or the real skill checkout's `bin/embedded-ddd`. Inspect `--help` for options. It records source availability independently and continues collecting a remote log when a local serial file fails. It does not classify business health or provide background notifications after the task ends. When unavailable, carry out the same observations with the existing project and system tools.

## Follow the evidence

| Observation | Next useful evidence |
| --- | --- |
| Deployment timeout/reconnect | Actual installed artifact, transaction receipt and boot/process identity; do not replay installation |
| Application crash/restart | Previous log segment, exit signal, kernel OOM evidence and matching core/executable |
| Process alive but unresponsive | Thread state, wait channels, CPU/memory and bounded GDB stacks if pausing is in scope |
| Missing event or callback | Evidence on both sides of its producer/consumer boundary; readiness, ordering and delivery |
| Hardware/driver symptom | Relevant kernel/driver/Proc evidence and real hardware preconditions |

Use a single falsifiable hypothesis to choose the next probe. Escalate to GDB when stacks, memory or a core would resolve the uncertainty; read [debugger escalation](references/debugger-escalation.md) at that point. Do not use process-altering debugger calls as routine log inspection.

## Completion

Explain the observation, supporting evidence, likely fault boundary and remaining uncertainty. Separate confirmed facts from hypotheses and missing coverage. If a fix is authorized, reproduce the affected behavior and verify it at the appropriate host/device boundary. Finish with the actual device result and any unresolved acceptance step, not merely a collection success message.
