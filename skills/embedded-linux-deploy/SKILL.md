---
name: embedded-linux-deploy
description: Build, transfer and deploy an embedded Linux application or firmware through its project's existing installer, with automatic device log collection and post-deployment verification. Use for board deployment, upgrade validation, or following a developer's deployment.
---

# Embedded Linux deployment

Complete the requested deployment and its agreed acceptance checks. Reuse confirmed target details and authorization from the current task. Keep product selection, partition layout, package signing, installation and rollback in the target project's existing tools.

## Establish the route

1. Read the relevant project instructions and deployment entrypoint. Resolve the target, product, actual artifact, installer and success criterion before changing the device. Look for a matching profile under `~/.config/embedded-linux/` or the project's configured location, or reuse its SSH alias; ask only for missing facts that change these choices.
2. Treat command access and file transfer as separate capabilities. Prefer the configured SSH route; Telnet and a free serial console are supported alternatives. File transfer can use SCP/SFTP, legacy SCP when explicitly selected, SSH streaming, or a project-owned HTTP/TFTP/NFS adapter. An SCP client alone does not establish interactive command access.
3. Check target identity and available space, then identify the log sources and artifact/receipt checks. A process being present does not prove the requested feature works.

When adapting an existing project or configuring an unusual transfer route, read [project adapters](references/project-adapters.md). Do not load adapter details for an already configured target.

## Observe, deploy, verify

- Start observation **before** invoking the installer. Record a serial-file cursor if available and collect application logs and target identity. Do not require the developer to separately ask for log monitoring.
- If the `embedded-ddd` CLI from this repository is available, inspect `--help` and use a local profile:

  ```sh
  embedded-ddd --profile /path/to/board.json deploy --output /path/to/new-run
  ```

  The helper executes `deploy.argv` in `deploy.cwd`, collects bounded evidence before/during/after the command, and runs the optional project verification command. Resolve the tool from its configured path or the real skill checkout's `bin/embedded-ddd`; do not assume a sibling checkout name or globally installed command. The skills also work with the project's own tools when this helper is unavailable.
- If the developer runs the installer, use the project's observer before telling them to start. Bind observation to their actual checkout, target and deployment report. Continue until its terminal result and requested observation window, timeout or cancellation. A completed chat does not provide persistent background monitoring.
- If the serial source is missing, empty, overwritten or has an unexplained gap, collect the configured application log over the available command connection immediately. Preserve the serial-source failure alongside the alternate evidence. Read-only sources may reconnect; never blindly repeat an installation command after a disconnect.
- Verify the actual deployed artifact/version or matching transaction receipt, running process identity and the requested behavior. Respect the project's existing rollback procedure if installation fails. Do not introduce raw flash writes or reset retained configuration to make a test pass.

## Completion

Report target, artifact/receipt evidence, installer outcome, application verification and relevant logs. Distinguish `installer_succeeded`, business acceptance and incomplete observations. A connection timeout after invoking an installer means its outcome needs reconciliation on the device; it is not permission to reinstall. Clean up only resources created for this task and leave the requested delivered application in place.
