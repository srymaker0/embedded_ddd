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
