# Debug modes

## Native GDB on the board

Set `gdb.native` in the local profile to the board executable. The helper requires a POSIX shell, `/proc`, `sha256sum` and a `timeout` supporting `-s TERM`. BusyBox without GNU `timeout -k` is supported. No GDB Python, debugger daemon or MCP server is required.

Check available RAM as well as storage. Loading many application/shared-library symbols can exhaust a small board's memory. Prefer host GDB plus gdbserver for rich symbols on such targets. For a bounded native snapshot, `gdb.auto_solib_add: false` suppresses automatic shared-library symbol loading; expect unresolved library frames and potentially incomplete unwinding, and record that limitation. An incomplete unwind alone does not establish stack corruption. In a controlled session, loading just a selected library with `sharedlibrary <pattern>` can supply its symbols within a smaller budget. Do not repeatedly retry a debugger killed by OOM with the same symbol policy.

The automated helper intentionally performs a fixed inspection sequence. For an interactive experiment use the configured terminal and ordinary GDB with `--nx --nh`; explicitly disable auto-loading before opening an executable. Always arrange a bounded stop, detach and verify process identity/state afterwards. The helper's timeout is a recovery attempt, not proof of recovery; `gdb-result.json` records the post-check separately.

To stage a supplied debugger, choose a non-production destination with enough space, then use:

```sh
embedded-ddd --profile /path/to/board.json put /path/to/native-gdb /task-owned/path/gdb --executable
```

The tool verifies SHA256 before replacing the destination. It does not change the loader or system libraries. Verify interpreter/library compatibility rather than copying arbitrary development libraries over the board's runtime.

A profile may retain `gdb.local` as a hint to the agent for an already prepared host-side debugger file. The snapshot command does not upload it automatically. If `gdb.native` is absent on the target, stage the compatible local file first, and remove task-only board files after the experiment when they are no longer needed.

## Host GDB and gdbserver

Use a host-executable cross/multiarch GDB that supports the target, plus compatible target `gdbserver`. Keep the unstripped executable, exact root filesystem libraries and source mapping on the host. Set `sysroot` and, when needed, `substitute-path` before drawing source-level conclusions.

Use the project's established debugger connection. GDB supports `target remote | command`, and `gdbserver` supports standard-I/O transport; an SSH pipe can avoid opening a target TCP listener. If using a TCP listener, restrict its reachability through the actual network setup rather than assuming that a host string in `gdbserver` makes it private. Verify which process owns the session before cleanup. Automated helper support currently covers native snapshots; this mode uses normal GDB commands.

## Offline core

Preserve the core, original executable, build IDs, exact shared libraries and crash metadata. Open them using a host GDB that supports the target architecture. Begin with all-thread backtraces and the faulting thread's registers; mismatched libraries/symbols must be resolved before attributing a source location. An offline core needs no live device attachment.

The GDB manual is authoritative for [attachment and detachment](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Attach.html), [remote connections](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Connecting.html) and [gdbserver](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Server.html).
