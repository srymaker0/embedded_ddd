# Install embedded-ddd

These instructions work for a person or an AI assistant installing from <https://github.com/srymaker0/embedded_ddd>.

## For AI assistants

Install for the assistant the user is currently using. Default to user scope; use project scope when requested. Install for both clients only when the user asks for both.

1. Find an existing checkout of this repository or clone it into a persistent location. If the user has not chosen a location, use `~/.local/share/embedded-ddd`. Check an existing directory's Git remote before reusing it; preserve local changes.
2. Run the appropriate command below to link the three skills. The script prints each installed path and refuses to replace a different existing skill. Resolve a conflict with the user rather than deleting their skill.
3. On Linux, also set up the command-line tool below unless the user requests skills only. On other hosts, install the skills and report that the helper's supported environment is Linux, including a Linux environment within WSL.
4. Verify that each printed path contains a readable `SKILL.md`. If the helper was installed, run `bin/embedded-ddd --help`. Report the installed skills, their location and whether the helper is available. If the client does not discover them, restart the client or start a new session.

Installation requires no device connection or device credentials. Board setup happens when the user requests a device task.

## Get the repository

Use Git and Python 3.8 or later on a host that supports symbolic links. The following commands use a POSIX shell:

```sh
git clone https://github.com/srymaker0/embedded_ddd.git embedded-ddd
cd embedded-ddd
```

Keep the checkout available: installed skills link to its files. The checkout can live wherever you normally keep development tools.

## Register the skills

Choose the command for your client:

| Client | Install for your user | Default destination |
| --- | --- | --- |
| Codex | `python3 scripts/link_skills.py --agent codex` | `~/.agents/skills/` |
| Claude Code | `python3 scripts/link_skills.py --agent claude` | `~/.claude/skills/` |

Claude Code's `CLAUDE_CONFIG_DIR`, when set, replaces `~/.claude` for user installation. These paths follow the [Codex skill documentation](https://developers.openai.com/codex/skills/) and [Claude Code skill documentation](https://code.claude.com/docs/en/skills).

To install only for one project, add its directory:

```sh
python3 scripts/link_skills.py --agent codex --project /path/to/project
```

Use `--agent claude` for Claude Code. Project installations use `.agents/skills/` for Codex and `.claude/skills/` for Claude Code. Add `--git-exclude` if you want the links ignored locally in that Git repository.

Repeated installation from the same checkout is safe. The installer preserves unrelated skills and reports a conflict if one of these names already points elsewhere:

- `embedded-linux-deploy`
- `embedded-linux-diagnostics`
- `embedded-linux-debug`

## Command-line tool

On a Linux development host, run these commands from the checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[console,serial]'
bin/embedded-ddd --help
```

The launcher uses this virtual environment automatically. The assistant can find it through the installed skill's real source path; adding it to `PATH` is optional. If a dependency cannot be installed, report the error and whether skill registration succeeded. The skills can also work with existing project tools.

SSH and file transfers use system OpenSSH clients. Telnet needs a system `telnet` client. Direct serial uses the installed PySerial and Pexpect dependencies; reading an existing terminal log does not require owning the serial port. Install a matching GDB only when a debugging task needs it.

The target needs a POSIX shell and `/proc`. Remote log collection uses `stat`, `tail` and `base64`; uploads use `sha256sum`. Native GDB snapshots also need a compatible GDB and `timeout` with `-s TERM` support. `inspect` checks the connection and reports available target tools before a device task.

If installation fails because `venv` is unavailable, install your distribution's Python venv package, then repeat the helper setup. If the skills do not appear, check the destination printed by the installer, any custom `CLAUDE_CONFIG_DIR`, and whether the checkout was moved or deleted. Reopen the client after correcting the links.

For profiles and commands, see the [README](README.md#optional-command-line-tool) or [中文说明](README.zh-CN.md#可选命令行工具).

## Update

In a clean checkout, fetch updates with:

```sh
git pull --ff-only
```

If you installed the helper, rerun its `pip install -e '.[console,serial]'` command to update dependencies. The skill links already point to the updated files; rerun the registration command if the set of skills changes. Preserve local modifications and resolve them before updating.

## Uninstall

Remove the three skill links from the destination used at installation, after checking that they point to this checkout. If you used `--git-exclude`, remove their entries from that repository's local Git exclude file. Once no installed links depend on it, you can remove the checkout and its `.venv`.
