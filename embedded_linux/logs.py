"""Bounded evidence collection, preserving gaps and observation timestamps."""

import base64
import hashlib
import json
import os
import shlex
import time
from pathlib import Path

from .profile import ToolError
from .transport import connect


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(str(temporary), 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary.replace(path)


def save_bytes(path, data):
    with path.open("wb") as stream:
        os.chmod(str(path), 0o600)
        stream.write(data)


def anchor(stream, offset):
    stream.seek(max(0, offset - 256))
    return hashlib.sha256(stream.read(min(offset, 256))).hexdigest()


class LocalLog:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.point = None

    def read(self, limit):
        if not self.path.is_file():
            raise ToolError("local log is absent or is not a regular file")
        with self.path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            identity = [info.st_dev, info.st_ino]
            previous = self.point
            reason = None
            if previous is not None:
                if previous["identity"] != identity:
                    reason = "replaced"
                elif info.st_size < previous["offset"]:
                    reason = "truncated"
                elif anchor(stream, previous["offset"]) != previous["anchor"]:
                    reason = "overwritten"
            context = previous is None or reason is not None
            start = max(0, info.st_size - limit) if context else previous["offset"]
            skipped = max(0, info.st_size - limit - start)
            start += skipped
            stream.seek(start)
            data = stream.read(min(limit, max(0, info.st_size - start)))
            end = start + len(data)
            self.point = {"identity": identity, "offset": end, "anchor": anchor(stream, end)}
        return {"state": "gap" if reason or skipped else ("data" if data else "empty"),
                "gap_reason": reason, "skipped_bytes": skipped, "context_only": context,
                "identity": identity, "byte_start": start, "byte_end": end}, data


def remote_log(session, path, limit):
    # base64 keeps console echo/CRLF conversion out of the actual log bytes.
    # Read metadata on both sides to avoid claiming a stable range across rotation.
    command = ("p={path}; before=$(stat -Lc '%d:%i:%s' \"$p\") || exit; "
               "printf '%s\\n' \"$before\"; tail -c {limit} \"$p\" | base64; "
               "after=$(stat -Lc '%d:%i:%s' \"$p\") || exit; "
               "printf '\\nEL_FILE_END:%s\\n' \"$after\"").format(path=shlex.quote(path), limit=limit)
    _, output = session.execute(command, timeout=10)
    try:
        before, body = output.strip().split("\n", 1)
        encoded, after = body.rsplit("\nEL_FILE_END:", 1)
        device, inode, size = [int(value) for value in before.strip().split(":")]
        data = base64.b64decode("".join(encoded.split()), validate=True)
    except (ValueError, TypeError) as exc:
        raise ToolError("remote log framing failed; stat, tail and base64 are required") from exc
    if len(data) > limit:
        raise ToolError("remote log exceeded its byte limit")
    if before.strip() == after.strip() and len(data) != min(size, limit):
        raise ToolError("remote log byte count does not match metadata; read is incomplete")
    return {"state": "snapshot" if before.strip() == after.strip() else "changed_during_read",
            "context_only": True, "identity": [device, inode],
            "byte_start": max(0, size - len(data)), "byte_end": size,
            "sha256": hashlib.sha256(data).hexdigest()}, data


class Collector:
    def __init__(self, profile, output, limit=65536, connector=connect):
        self.profile, self.output, self.limit = profile, Path(output), limit
        self.connector, self.session = connector, None
        self.local = {entry["name"]: LocalLog(entry["path"])
                      for entry in profile.get("logs", []) if entry["kind"] == "local"}
        self.previous_remote = {}
        self.report = {"target": profile["name"], "connection": profile["connection"]["type"],
                       "started_at": time.time(), "cycles": []}

    def connection(self):
        if self.session is None:
            self.session = self.connector(self.profile)
            try:
                check_identity(self.session, self.profile)
            except (ToolError, OSError):
                self.close()
                raise
        return self.session

    def close(self):
        if self.session is not None:
            self.session.close()
            self.session = None

    def tick(self):
        index = len(self.report["cycles"])
        cycle = {"observed_at": time.time(), "sources": []}
        # Each source is independent: missing/empty serial never prevents app-log collection.
        for entry in self.profile.get("logs", []):
            result = {"name": entry["name"], "kind": entry["kind"]}
            try:
                if entry["kind"] == "local":
                    state, data = self.local[entry["name"]].read(self.limit)
                else:
                    state, data = remote_log(self.connection(), entry["path"], self.limit)
                    previous = self.previous_remote.get(entry["name"])
                    if previous:
                        state["gap_detected"] = (state["identity"] != previous["identity"] or
                                                 state["byte_end"] < previous["byte_end"] or
                                                 state["byte_start"] > previous["byte_end"])
                        state["unchanged"] = (state["identity"] == previous["identity"] and
                                              state["sha256"] == previous["sha256"])
                    self.previous_remote[entry["name"]] = state.copy()
                result.update(state)
                if data and not state.get("unchanged"):
                    filename = "{:04d}-{}.log".format(index, entry["name"])
                    save_bytes(self.output / filename, data)
                    result["file"] = filename
            except (ToolError, OSError) as exc:
                result.update(state="unavailable", error=str(exc))
                if entry["kind"] == "remote":
                    self.close()
            cycle["sources"].append(result)
        try:
            _, identity = self.connection().execute(
                "uname -srmo; printf 'boot_id='; cat /proc/sys/kernel/random/boot_id; "
                "printf 'uptime='; cat /proc/uptime", timeout=10)
            filename = "{:04d}-identity.txt".format(index)
            save_bytes(self.output / filename, identity.encode("utf-8"))
            cycle["identity_file"] = filename
            for probe in self.profile.get("probes", []):
                code, output = self.connection().execute(probe["command"], timeout=10, check=False)
                filename = "{:04d}-{}.txt".format(index, probe["name"])
                save_bytes(self.output / filename, output.encode("utf-8"))
                cycle.setdefault("probes", []).append({"name": probe["name"], "returncode": code,
                                                       "file": filename})
        except (ToolError, OSError) as exc:
            cycle["identity_error"] = str(exc)
            self.close()
        self.report["cycles"].append(cycle)
        self.report["last_observed_at"] = time.time()
        write_json(self.output / "diagnostics.json", self.report)
        return cycle


def check_identity(session, profile):
    expected = profile.get("identity")
    if expected:
        _, output = session.execute(expected["command"])
        if expected["contains"] not in output:
            raise ToolError("target identity does not match this profile")
