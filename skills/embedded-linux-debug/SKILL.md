---
name: embedded-linux-debug
description: Debug embedded Linux processes with native GDB, a matching host GDB plus gdbserver, or an offline core. Use for thread stacks, breakpoints, state inspection and controlled function-call experiments on Linux targets.
---

# Embedded Linux Debug

Use the debugger already available for the target when it fits the task. Establish architecture, executable/symbol identity and what the experiment must prove before selecting a mode.

Reuse a matching target profile under `~/.config/embedded-linux/` or the project's configured location; do not ask again for an already confirmed device or debugger path.

## Select and prepare

- Inspect supplied tools with `file`/ELF headers and, on the appropriate machine, `--version`. Distinguish a host debugger, board-native debugger and `gdbserver`. Do not run an ARM ELF on the development host or assume GDB Python support.
- Prefer offline core analysis for a past crash, native GDB for a board with a compatible debugger, and host GDB plus `gdbserver` when that offers the matching symbols/toolchain. Read [debug modes](references/debug-modes.md) only for the selected mode's details.
- Verify the application executable and shared libraries against the deployed artifact using build IDs or exact artifact provenance. Debug information in the GDB executable does not supply application symbols. Report missing symbols and optimized-out values rather than inventing source-level certainty.
- If the debugger needs transfer, check board architecture, interpreter, dependencies and free space. Stage it in a task-owned directory with the selected transfer tool and verify its hash. A stripped copy of GDB can reduce deployment size; retain the provided original and the application's symbols.

## Inspect a live process

Attaching pauses the process. Establish whether that pause and any watchdog or hardware effect are covered by the task; retain previously given authorization. Read-only stack inspection and a function call have different effects.

For a configured native debugger, the optional repository helper runs a bounded snapshot:

```sh
embedded-ddd --profile /path/to/board.json gdb-snapshot --pid 1234 --output /path/to/new-run
```

Use the configured helper path, or `../.embedded-ddd/bin/embedded-ddd` relative to this skill directory when the optional helper is installed. It checks process identity and existing tracers, disables automatic GDB init scripts, captures all-thread stacks, detaches and checks the same process has resumed. A failed recovery check remains unresolved even if GDB returned zero. If the helper is unavailable, perform these steps using ordinary GDB commands and the project connection tools.

For breakpoints, stepping or calls, define the hypothesis, stop location, expected evidence and cleanup before starting. Do not hold an unrelated lock or wait for a stopped thread. Inspect a known, side-effect-free expression before considering a call; C/C++ getters can also have side effects. Record injected events as simulated inputs. They do not prove the real external input path works.

## Finish the experiment

Remove task-created breakpoints, detach/continue the intended process, stop only task-created debugger/server processes and verify application operation. On a connection loss, inspect `TracerPid`, process start and state before reconnecting or issuing recovery commands; never blindly send `SIGCONT` to an unrelated PID.

GDB can replace many one-off preload/FIFO harnesses for inspection and controlled calls. Keep repeatable acceptance scenarios on existing public CLI/IPC/network interfaces when possible. A debugger snapshot or injected callback does not prove timing, networking or hardware behavior.
