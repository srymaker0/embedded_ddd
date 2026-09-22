<p align="center">
  <img src="assets/embedded-ddd.svg" alt="embedded-ddd — Deploy · Diagnostics · Debug" width="100%">
</p>

<p align="center">
  <strong>Deploy · Diagnostics · Debug</strong><br>
  A practical development loop for embedded Linux, built for AI coding assistants.
</p>

<p align="center">
  <a href="README.zh-CN.md">中文</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#the-ddd-loop">The DDD loop</a> ·
  <a href="INSTALL.md">Installation</a> ·
  <a href="LICENSE">MIT License</a>
</p>

**embedded-ddd** gives Codex three connected skills for working with real devices. Supply the device address and the task; the assistant uses your project's tools and available SSH, Telnet or serial connection to deploy builds, investigate failures and inspect the running program.

## The DDD loop

DDD stands for **Deploy, Diagnostics, Debug**. Observe a deployment, use the evidence to narrow down a problem, then inspect the program where that evidence leads. Verify the fix on the device to complete the loop. Start with whichever stage your task needs.

| Stage | Purpose | Skill |
| --- | --- | --- |
| **Deploy** | Run the existing installer, observe before and after, and verify what actually runs | [embedded-linux-deploy](skills/embedded-linux-deploy/SKILL.md) |
| **Diagnostics** | Correlate serial, application and kernel logs with process state to locate the failure | [embedded-linux-diagnostics](skills/embedded-linux-diagnostics/SKILL.md) |
| **Debug** | Inspect stacks, breakpoints, program state or a core with GDB; verify recovery after a live session | [embedded-linux-debug](skills/embedded-linux-debug/SKILL.md) |

The three skills share target details and evidence across the task. A missing serial log leads to other available log sources. A lost deployment connection calls for checking the device's actual state. A completed debug session includes checking that the process resumed.

## Quickstart

Paste this into Codex:

```text
Install embedded-ddd from https://github.com/srymaker0/embedded_ddd
for Codex. Follow INSTALL.md in the repository.
```

Installation defaults to your user account so the skills are available across projects. Add “install for this project only” to limit their scope. [INSTALL.md](INSTALL.md) covers manual installation, updates and removal.

Then work in your application project:

```text
Deploy this build to 192.0.2.10 and check its startup logs.
```

```text
The application keeps restarting. Use the serial and device logs to find out why.
```

```text
Use GDB to inspect the blocked threads, then detach and verify the process resumed.
```

Codex can select the relevant skill automatically. Invoke one directly with `$embedded-linux-deploy`, `$embedded-linux-diagnostics` or `$embedded-linux-debug`.

## Work with your development environment

Use your existing SSH aliases, keys, terminal logs and deployment scripts. Device details can come from the conversation, project configuration or a private [connection profile](examples/).

The current skills cover **embedded Linux**. Debugging supports native GDB, host GDB with gdbserver, and offline cores. Live debugging pauses the selected process. RTOS and bare-metal targets are outside the current scope.

### Optional command-line tool

The skills work with existing tools. The included `embedded-ddd` helper automates connections, transfers, log collection, deployment observation and native GDB snapshots on a Linux development host. See [setup instructions](INSTALL.md#command-line-tool).

Copy an [SSH](examples/ssh.json), [Telnet](examples/telnet.json) or [serial](examples/serial.json) profile to a private path, replace the placeholders, then run:

```sh
bin/embedded-ddd --profile /path/to/board.json inspect
bin/embedded-ddd --profile /path/to/board.json collect --output output/logs-001 --duration 30
bin/embedded-ddd --profile /path/to/board.json deploy --output output/deploy-001
bin/embedded-ddd --profile /path/to/board.json gdb-snapshot --pid 1234 --output output/debug-001
```

Use a new output directory for each run. Profiles execute configured commands, so use trusted local configuration. Store credentials in SSH configuration or a separate private password file, and review collected logs before sharing.

Command access and file transfer are configured separately. Transfers support SFTP, SCP, SSH streams and HTTP uploads with SHA256 verification. Deployment uses the project's installer and its update and rollback behavior. Remote GDB and core analysis use standard debugger tools under skill guidance.

## Development

After installing the helper, run the host tests:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The full suite uses GCC, GDB, OpenSSH clients and server, a Telnet client, and curl. Missing optional tools are reported as skips. Tests cover connections, transfers, log continuity, deployment lifecycle, debugger recovery and skill installation. [Evaluation scenarios](evals/scenarios.json) provide cases for reviewing assistant behavior.

Report problems or propose improvements through [GitHub Issues](https://github.com/srymaker0/embedded_ddd/issues) and pull requests. Include the host and target environment, reproduction steps, and relevant logs with private data removed.

## License

[MIT](LICENSE).
