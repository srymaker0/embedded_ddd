# Debugger escalation

Prefer a core with its matching executable/libraries for a past crash. Prefer a short all-thread stack snapshot for a currently stuck process. Check whether a watchdog or actuator makes a pause material; reuse authorization already covering that operation and only ask about genuinely missing scope or target conditions.

Before attaching, record executable identity, `/proc/PID/stat` start time, `TracerPid` and state. Do not steal a process from another debugger or resume a process that was intentionally stopped. After detaching, verify the same process is untraced and no longer stopped. If access is lost, report recovery as unverified until fresh device evidence resolves it.

Do not infer timing or concurrency correctness from a paused process. A debugger `call` can take locks, allocate memory, trigger hardware or wait for another stopped thread. Function injection belongs to an explicitly chosen experiment with known preconditions; it cannot replace a real provisioning, transport or hardware acceptance test.
