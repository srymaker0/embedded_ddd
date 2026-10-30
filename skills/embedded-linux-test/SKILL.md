---
name: embedded-linux-test
description: Select and run embedded Linux regression tests and acceptance checks across host, emulation and device environments. Use to verify a fix or deliverable and distinguish executed coverage from hardware checks still needed.
---

# Embedded Linux test and acceptance

Verify the requested behavior through the project's existing tests and acceptance
entrypoints. Select an environment that can observe that behavior; a successful
build or installation is evidence for only that step.

## Choose the observable check

- Establish the original trigger, relevant initial state, expected result and
  timeout/failure condition. For a regression, inspect the production path the
  test executes and the dependencies its fixture replaces.
- Reuse existing tests that cover the changed behavior. Add a regression test only
  when a concrete uncovered failure warrants one; do not mirror implementation
  details or create a framework for a routine edit.
- Use the smallest sufficient environment and the project's actual runner:

  | Environment | What it can establish |
  | --- | --- |
  | Host test | Behavior of the production code linked into that test, under its stated fixtures |
  | Cross-build | Compile/link compatibility for the selected target; no executed behavior |
  | User-mode emulation | Target userspace execution under the emulator's supported ABI and host kernel |
  | System emulation | Behavior of the guest software and the devices actually modeled |
  | Physical target | The observed scenario on the identified hardware, software and configuration |

For fixture boundaries, negative cases or device acceptance, read
[acceptance checks](references/acceptance.md).

## Execute and reconcile

- Verify executable architecture and runtime requirements before choosing a host,
  emulator or device command. Preserve the selected product and configuration.
- Run the selected checks and retain their command, environment and result. Check
  that the runner discovered and executed the intended cases; zero matches,
  disabled cases and dependency skips are not passes.
- Separate an assertion failure from a setup, dependency or transport failure.
  Locate whether the cause is the current change, an existing baseline or an
  environment limitation before modifying code or broadening the test run.
- On a device, connect evidence to the actual artifact, boot/process and runtime
  configuration. Exercise the requested real input and observe its output. Keep
  a simulated callback, a driver write, hardware behavior and external service
  acknowledgement distinct when the task depends on those boundaries.
- Use existing authorization for deployment, restart or fault injection; a request
  to run host tests does not authorize those operations. If a required target or
  external action is unavailable, finish independent checks and describe the
  remaining scenario and pass condition.

## Report coverage

State which behavior passed or failed, which cases actually ran, what their
fixtures replaced, and what remains unverified. For an expected failure or
rollback, require both the intended failure and the specified recovered state.
Do not turn an unexecuted acceptance plan into a successful result.

Reuse evidence whose relevant code, artifact, configuration and environment are
unchanged. Recheck only the affected behavior after further changes. Finish any
already requested and authorized device acceptance using project tools and, when
available, `embedded-linux-deploy`, `embedded-linux-diagnostics` or
`embedded-linux-debug`; choose them only when the actual operation needs them.
