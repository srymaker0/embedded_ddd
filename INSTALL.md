# Install embedded-ddd

Install from <https://github.com/srymaker0/embedded_ddd> into the application project where you want to use the skills.

## For AI assistants

1. Work from the application project directory. Use the project installation command below to download the three skills from GitHub into `.agents/skills/`. Preserve unrelated skills and any local edits to an existing installation.
2. Verify that each skill has a readable `SKILL.md` in its own directory. The installed directories must contain the files themselves and remain usable after the temporary download is removed.
3. Finish the default installation after copying the three skills. Use the project's existing connection, deployment and debugging tools. Install the optional helper only when the user requests it or a specific device task needs capabilities that the existing tools do not provide. Reuse a suitable installed helper environment before creating another one.
4. Check skill discovery and report the three installed paths. If a helper was separately requested or needed, run its `--help` and report its location as well. Start a new session if the client has not refreshed its skills.

Installation does not require a device connection or credentials. Configure a target when the user requests a device task.

## Install the skills

With Node.js, npm and Git available, run this command from your application project:

```sh
npx --yes skills add srymaker0/embedded_ddd --agent codex \
  --skill embedded-linux-deploy embedded-linux-diagnostics embedded-linux-debug --copy --yes
```

The installer downloads the skills and places their files directly in:

```text
your-project/
└── .agents/
    └── skills/
        ├── embedded-linux-deploy/
        │   ├── SKILL.md
        │   ├── agents/
        │   └── references/
        ├── embedded-linux-diagnostics/
        │   ├── SKILL.md
        │   ├── agents/
        │   └── references/
        └── embedded-linux-debug/
            ├── SKILL.md
            ├── agents/
            └── references/
```

These are ordinary directories. Default installation adds only these three skills; it does not create a Python environment. Codex discovers them through its project skill directory. A permanent repository checkout and skill symlinks are unnecessary.

The installer records the source of each skill in `skills-lock.json` at the project root. Keep that file with the skills when sharing the installation with a team. For a private local installation, use the application's local Git exclude file to ignore these three directories, the optional `.agents/skills/.embedded-ddd/` environment and `skills-lock.json` as needed. Preserve existing ignore rules.

Check discovery with:

```sh
npx --yes skills list --agent codex
```

If Node.js is unavailable, use Codex's skill installer with this repository's `master` branch, the three `skills/embedded-linux-*` paths and an explicit destination of `<project>/.agents/skills`. It copies the same skill directories. Track updates manually when using that route.

## Command-line tool

The skills work with existing project tools. Set up the shared `embedded-ddd` helper only when a device task needs it or you choose to use it. It supports Linux, including WSL, with Python 3.8 or later.

If a suitable environment already provides `embedded-ddd`, use that command. Otherwise, the following commands create an optional environment inside the project's skill directory. Run them from the application project:

```sh
python3 -m venv .agents/skills/.embedded-ddd
.agents/skills/.embedded-ddd/bin/python -m pip install --upgrade pip
.agents/skills/.embedded-ddd/bin/python -m pip install \
  'embedded-ddd[console,serial] @ git+https://github.com/srymaker0/embedded_ddd.git@master'
.agents/skills/.embedded-ddd/bin/embedded-ddd --help
```

This installs the Python package and its dependencies inside `.agents/skills/.embedded-ddd/`. The three skills share this environment; no persistent source checkout is needed. Use `.agents/skills/.embedded-ddd/bin/embedded-ddd` from the project directory, or `../.embedded-ddd/bin/embedded-ddd` relative to an installed skill directory. Adding the tool to `PATH` is optional.

SSH and file transfers use system OpenSSH clients. Telnet needs a system `telnet` client. Direct serial uses PySerial and Pexpect; reading an existing terminal log does not require owning the serial port. Install a matching GDB when a debugging task needs it.

The target needs a POSIX shell and `/proc`. Remote log collection uses `stat`, `tail` and `base64`; uploads use `sha256sum`. Native GDB snapshots need a compatible GDB and `timeout` with `-s TERM` support. `inspect` checks the connection and reports available target tools before a device task.

If `venv` is unavailable, install your distribution's Python venv package and repeat the helper setup. If dependency installation fails, report the error and whether the skills themselves were installed successfully. Profiles and command examples are in the [README](README.md#optional-command-line-tool) and [中文说明](README.zh-CN.md#可选命令行工具).

## Update

Preserve any local skill edits before updating. From the application project, update these three skills:

```sh
npx --yes skills update embedded-linux-deploy embedded-linux-diagnostics embedded-linux-debug --project --yes
```

If you installed the helper, update its package separately:

```sh
.agents/skills/.embedded-ddd/bin/python -m pip install --upgrade \
  'embedded-ddd[console,serial] @ git+https://github.com/srymaker0/embedded_ddd.git@master'
.agents/skills/.embedded-ddd/bin/embedded-ddd --help
```

Each project owns its installed copies and updates independently.

## Uninstall

From the application project:

```sh
npx --yes skills remove embedded-linux-deploy embedded-linux-diagnostics embedded-linux-debug --agent codex --yes
```

If you installed the optional helper, remove `.agents/skills/.embedded-ddd/` after confirming it is this installation's virtual environment. For a manual skill installation, remove the three skill directories directly. Preserve unrelated skills, lockfile entries and Git exclude rules.
