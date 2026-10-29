# Project adapters

Use the project's executable deployment command as the adapter. The generic helper owns observation and command lifecycle; it must not duplicate the project's update transaction, partition policy or signature handling.

Profiles are trusted local configuration, not remote instructions. `deploy.argv` is an argument array executed without a host shell; `deploy.cwd` identifies the real checkout. `deploy.verify_command` is an explicit target shell command whose exit status defines an additional project check. Record what installer success already guarantees in `deploy.success_means`.

A board profile should distinguish:

| Concern | Configuration or project owner |
| --- | --- |
| Command connection | `connection.type`: `ssh`, `telnet`, `serial` |
| SSH keys, host checking, jump host | Existing SSH config/agent; optional `connection.config_file` |
| Console authentication | `user`, optional `password_file` owned by the user with mode 0600 |
| File transfer | `transfer.method`: `sftp`, `scp`, `ssh-stream`, `http` |
| Target identity check | `identity.command` and expected `identity.contains` |
| Existing terminal log | `logs` entry with `kind: local`; do not open that terminal's serial port |
| Target application log | `logs` entry with `kind: remote` and explicit target path |
| Deployment and acceptance | Project command, package/slot receipt, version and behavior check |

Modern `scp` normally uses SFTP, whereas older clients default to the legacy protocol. The helper selects protocols explicitly: `sftp` uses the SFTP client and `scp` uses `scp -O`. If a small SSH server has no SFTP subsystem, select `scp` only if it has the legacy SCP executable, or use `ssh-stream` when it can execute a POSIX shell. Do not disable SSH host checking or fall back to plaintext Telnet after an authentication error.

HTTP upload serves only one selected file at a random URL for the duration of the transfer. It requires the board to reach the host's selected interface. The helper verifies SHA256 before renaming its temporary upload. This transfers a file; installing an application/firmware still belongs to the project adapter. For Telnet-only boards, use a trusted lab network. For large core dumps, choose an existing project transfer path or SSH file transfer rather than sending a binary over a text console.

Look at the repository's `examples/*.json` for minimal SSH, Telnet and direct serial profiles. Replace placeholders in a private copy. Addresses, absolute development paths, credentials and raw device evidence do not belong in the public skill repository.

## Build and artifact provenance

Use the project's supported build and packaging entrypoints. When the task already supplies a package, verify that package without rebuilding it merely to repeat completed work.

- Check that the build cache belongs to the intended checkout, product, toolchain and configuration. For CMake, inspect `CMAKE_HOME_DIRECTORY` and the relevant configuration in `CMakeCache.txt`; a directory name alone does not establish its source.
- Determine whether installation and packaging reuse the last successful build. Rebuild changed source before generating a deliverable; reinstall changed configuration/resources when the project requires it. A packaging command returning zero does not establish that it recompiled the changes.
- For a replaced library, SDK object or kernel module, follow the formal input selection, build/link, patch/copy and packaging steps. Check whether an old patch still transforms the replacement. Inspect the relevant file inside the final archive or image, not only the temporary build or staging directory.
- Distinguish application-only and full-firmware packages by their actual components. Compare the affected packaged files with the expected version, build ID or hash. A commit label, timestamp or configuration manifest alone does not establish that uncommitted source changes entered the package.

## Acceptance evidence

Select checks for the original trigger and expected behavior. Confirm which production implementation a host test executes and which external conditions its fixture replaces. If the changed implementation is replaced by a stub in that test, use an existing test or target scenario that actually covers it. Cross-compilation establishes build compatibility; user-mode emulation does not establish driver, electrical or mechanical behavior. Count executed cases separately from skipped cases and build-only targets.

Match the result to the requested path. Installation success does not establish that the application's download protocol, upgrade notifications or backend workflow succeeded. A debugger-injected event does not exercise the real external input. For an expected failure or rollback case, check both the intended failure and the recovered application/state before calling the case passed.

Reuse evidence when the relevant artifact, configuration and environment are unchanged. Verify newly generated package contents even if the same component already passed a board test; keep that packaging result distinct from the earlier hardware result.
