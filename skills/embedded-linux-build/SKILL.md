---
name: embedded-linux-build
description: Build and package embedded Linux software with the project's existing tools. Use for cross-compilation, build or link failures, and checking whether changed components entered a deliverable.
---

# Embedded Linux build

Produce the requested executable, library, staging tree or package through the
project's supported build entrypoint. A build task can finish on the development
host; it does not imply deployment.

## Resolve the build inputs

- Read the relevant project instructions and build entrypoint. Identify the
  requested product/board, configuration, compiler, sysroot and output. Reuse
  confirmed selections; a directory name or an old manifest is not enough.
- Check whether the build cache belongs to this checkout and configuration before
  reusing it. Identify shared staging or output directories before writing them.
- Determine which steps compile, install into staging, package and create images.
  An install or package command may reuse an earlier successful build.
- For a dependency, SDK, prebuilt library or kernel module change, trace the
  selected input through linking, patching, copying and final packaging. Keep
  product choices and build commands in the consuming project.

For cache, toolchain or package-content questions, read
[build checks](references/build-checks.md).

## Build and inspect

- Run the existing entrypoint for the requested output. Rebuild affected source
  before staging it; reinstall changed resources or defaults as the project
  requires. Preserve an explicitly supplied artifact instead of rebuilding it
  merely to repeat completed work.
- On failure, inspect the first actionable compiler, linker or tool error and its
  command. Distinguish a changed source/dependency from a missing host tool or a
  mismatched SDK. Follow the failing input; do not switch products, disable checks
  or clear shared output to obtain a successful exit.
- Inspect the actual final deliverable, including affected files inside an
  archive or image. Relate it to the requested source/configuration with build
  records and the relevant hashes or build IDs. A commit label or timestamp alone
  does not prove that uncommitted changes reached the package.
- Use architecture-aware inspection tools for target artifacts. Never run a
  foreign executable directly on the host to check whether it works.

## Continue from the result

Report the configuration, executed commands, outcome and final artifact paths,
plus the evidence that affected files reached those artifacts. Keep compilation,
package inspection and executed tests distinct.

When the task includes behavior verification, use `embedded-linux-test` if
available, or the project's existing tests. When it includes device deployment,
carry the artifact identity and pending checks into `embedded-linux-deploy` if
available, or the project installer. Neither skill is required for a build-only
task, and missing skills do not prevent use of the project's documented tools.
