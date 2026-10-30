# Build and artifact checks

Read only the section relevant to the requested build or failure.

## Cache and toolchain identity

Use the project's wrapper, presets or environment setup before inferring raw
build-system commands. Check generated state against the current checkout:

- For CMake, inspect `CMAKE_HOME_DIRECTORY`, the compiler/toolchain file, sysroot,
  build configuration and selected product options in the existing cache.
- For Make or a vendor wrapper, follow the selected configuration, compiler
  variables and actual compile/link commands. Inspect the relevant recipe before
  relying on a dry run; recursive recipes may still execute commands.
- An SDK shell, `PATH`, compiler prefix and sysroot must describe the same target.
  `file` and the selected toolchain's `readelf` help identify architecture,
  interpreter, required shared libraries and ABI attributes. A matching CPU name
  alone does not establish libc, floating-point ABI or loader compatibility.
- Host programs used during the build need a host compiler and runnable host
  dependencies. They are separate from the target executable and its libraries.

If a cache is incompatible, use the project's supported reconfiguration or a
separate task-owned build directory. A clean build should address a demonstrated
stale-input problem, not hide which input caused a failure.

## Follow a component into the deliverable

For the changed component, inspect the relevant transitions:

| Transition | Evidence to check |
| --- | --- |
| Source or dependency to selected input | Configuration and dependency selection, including copied or prebuilt inputs |
| Selected input to compiled/linked output | Actual compile/link command and output; library resolution for the affected symbol |
| Output to staging | Install/copy/strip/patch rules and the staged component |
| Staging to archive or image | Package inputs and the corresponding file in the final deliverable |

Compare hashes where the bytes should be identical. When stripping, signing or
another transformation changes the bytes, follow that transformation and compare
the expected result; do not label every hash difference as stale content. Retain
matching unstripped binaries and debug files when later debugging needs them.

Inspect an archive in a task-owned directory or use an available read-only image
inspection tool. If the required extractor or signing key is unavailable, report
the last verified stage and the missing final check. Staging inspection alone
does not establish the contents of the image.

Application-only and full-firmware outputs can contain different components.
Check which one the task needs and whether defaults, resources, shared libraries,
kernel modules or companion firmware are included. Packaging new defaults does
not establish whether an installed device will retain or migrate old settings.

## Build failures

Use the failing invocation and selected inputs to locate the boundary. Common
distinctions include a missing host generator versus a target library, headers
from one SDK versus libraries from another, unresolved symbols versus a runtime
loader dependency, and a source change versus stale generated configuration.
Correct the authoritative input or invocation; editing generated output only
proves a temporary workaround. Rerun the affected build and package checks after
the correction.
