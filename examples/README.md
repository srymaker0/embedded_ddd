# A complete DDD loop on Linux

This is the device-workflow example in embedded-skills. It executes fixed build,
deployment and verification commands without calling a model; it is not an
evaluation of how an assistant follows the build or test skill.

This example provides its own application and installer. It needs no physical board
and uses only temporary localhost SSH access. Run it as an ordinary development user
on Linux, with Python 3.8+, GCC, GDB and OpenSSH clients/server available.

On Debian/Ubuntu, the system packages are `gcc gdb openssh-client openssh-server`.
Some minimal containers also need an administrator to create `/run/sshd`. The script
does not install packages, start a system service or change system SSH configuration.
If ptrace or local SSH servers are prohibited in your environment, the example fails
with evidence instead of disabling host protections.

From a source checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[console,serial]'
.venv/bin/python examples/linux_lab.py run --output output/linux-lab-001
```

Choose a new output directory each time. The script:

1. Builds two versions of [the application](linux_lab_app.c), with debug symbols.
2. Creates temporary SSH keys, explicit known-hosts verification and a random
   loopback port. It exposes only the current development user's SSH account.
3. Transfers each artifact with SFTP and SHA256 verification, then uses the example
   project's installer through the helper's `deploy` command. Acceptance compares
   the expected artifact, receipt, process identity and advancing heartbeat.
4. Sends `SIGUSR1` to simulate a blocked worker. Collection preserves the missing
   serial source and captures the available application log.
5. Captures all-thread GDB stacks and verifies the same process is no longer traced
   or debugger-stopped. `wait_for_recovery` should appear in the stack.
6. Sends the example's `SIGUSR2` recovery input and verifies advancing heartbeats.
7. Stops only its own application/server and removes the temporary SSH credentials.

`result.json` summarizes the outcome. `deploy-v1/`, `deploy-v2/`, `diagnostics/` and
`debug/` retain the helper's original evidence. A collection result of `partial` is
expected: the example intentionally has no serial capture. Profiles reference keys
that are removed during cleanup, so rerun the example to obtain a fresh target.

The target is a real native Linux process, but its fault and recovery inputs are
synthetic. This does not validate cross-architecture symbols, physical serial links,
device power control, watchdog effects, flash installation or a product's behavior.
The application explicitly permits ptrace for this example; do not copy that policy
into production software without reviewing its implications.
