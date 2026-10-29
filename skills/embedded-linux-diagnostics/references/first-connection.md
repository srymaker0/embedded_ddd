# First connection

Use this when the project has no working device configuration, or a new developer
cannot reproduce the connection. Reuse existing project commands and credentials
before introducing another tool or profile.

## Establish the minimum facts

Read the project's device/build documentation and existing deployment scripts.
Reuse the address, product and authorization already supplied. Discover the command
connection (SSH alias, Telnet, or serial device and baud rate), application process,
log sources and intended task. Ask only for missing facts that block that task.
An IP address does not identify an installer, product variant or acceptance check.

SSH command access does not imply SFTP is available. Select a supported transfer
method independently; SCP in the optional helper uses legacy SCP, and SSH streaming
needs only a shell and `cat`. Reuse SSH keys/config/agent authentication. Telnet and
serial passwords belong in a separate owner-only file with mode 0600. Do not place
credentials in a profile, prompt or command line.

## Save a reusable configuration when useful

Templates travel with this skill, including installations that contain no source checkout:

- [SSH](../assets/profiles/ssh.json)
- [Telnet](../assets/profiles/telnet.json)
- [Serial console](../assets/profiles/serial.json)

Resolve these paths from this reference file. Copy the chosen template to the
project's existing private configuration location, or `.agents/embedded-ddd.local.json`.
Replace placeholders with observed facts and remove irrelevant optional sections.
Exclude private profiles and evidence from Git according to the project's convention.
Paths in a profile are interpreted from the invoking working directory (or as
absolute paths), not from the JSON file's directory. `~` is supported for host paths.

Add an `identity` object with a read-only `command` and an expected nonempty
`contains` string when the target exposes a stable identifier. Record the executable
and build identity separately. Set `deploy.argv` only to the actual project-owned
installer; its `verify_command` must check the project's receipt/artifact and service
expectations. A PID alone does not prove the requested artifact is installed.

File logs go in `logs`; read-only process/service checks may go in `probes`.
For a journal-only target, use the project's `journalctl` workflow instead of
inventing a file log to satisfy the helper. A terminal's saved serial file is a
local log and does not require opening the serial port again.

## Check the requested operation

If the optional helper is present, inspect only the operation being attempted:

```sh
embedded-ddd --profile .agents/embedded-ddd.local.json inspect --local --for collect
embedded-ddd --profile .agents/embedded-ddd.local.json inspect --for collect
```

Use `--for deploy`, `--for put` or `--for gdb-snapshot` when needed. The default is
connection-only. JSON output lists passed checks, warnings, failures and unverified
conditions. Exit 2 means a required check failed; `--local` never connects and leaves
`ready` null. Inspection executes the configured identity command but never the
installer, acceptance command, probes or a GDB attach. Keep identity commands read-only.
Opening a serial console can toggle control lines; use `--local` first if that matters.

Without the helper, use existing connection tools to check the same relevant facts:
target identity, readable evidence, the real installer path, or debugger compatibility.
Do not install the helper merely because this guide names it.

Finish by stating the working connection and evidence sources, the selected task's
remaining prerequisites and the next useful action. Missing serial evidence should
lead to available application logs, not block the whole investigation. Readiness
does not prove application health, a successful deployment or functional acceptance.
