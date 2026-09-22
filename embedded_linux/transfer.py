"""Explicit transport selection and SHA256-verified file staging."""

import hashlib
import http.server
import secrets
import shlex
import socket
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

from .profile import ToolError
from .transport import SSH


@contextmanager
def serve_one_file(path, bind_address):
    token_path = "/" + secrets.token_hex(20)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != token_path:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(path.stat().st_size))
            self.end_headers()
            try:
                with path.open("rb") as source:
                    while True:
                        block = source.read(65536)
                        if not block:
                            break
                        self.wfile.write(block)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer((bind_address, 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://{}:{}{}".format(bind_address, server.server_address[1], token_path)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def source_address(host):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.connect((host, 9))
        return connection.getsockname()[0]


def put_file(session, profile, source, destination, executable=False, timeout=120):
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ToolError("upload source must be a regular file")
    if not destination.startswith("/") or any(c in destination for c in "\x00\r\n"):
        raise ToolError("destination must be an absolute target path without control characters")
    if any(c in str(source) for c in "\x00\r\n"):
        raise ToolError("source path must not contain control characters")
    method = profile.get("transfer", {}).get("method", "sftp" if isinstance(session, SSH) else "http")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    expected = digest.hexdigest()
    temporary = destination + ".part-" + secrets.token_hex(8)
    quoted = shlex.quote(temporary)
    try:
        if method in ("sftp", "scp"):
            if not isinstance(session, SSH):
                raise ToolError("SCP requires an SSH command connection")
            target_host = session.config["host"]
            if ":" in target_host:
                target_host = "[" + target_host + "]"
            destination_host = ((session.config["user"] + "@") if session.config.get("user") else "") + target_host
            if method == "sftp":
                def batch_quote(path):
                    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'
                batch = "put {} {}\n".format(batch_quote(source), batch_quote(temporary))
                result = subprocess.run(["sftp", "-b", "-"] + session.options(scp=True) + [session.destination],
                                        input=batch.encode("utf-8"), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, timeout=timeout)
            else:
                result = subprocess.run(["scp", "-B", "-O"] + session.options(scp=True) +
                                        [str(source), destination_host + ":" + quoted],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if result.returncode:
                raise ToolError(method + " failed: " + result.stderr.decode("utf-8", "replace"))
        elif method == "ssh-stream":
            if not isinstance(session, SSH):
                raise ToolError("ssh-stream requires an SSH connection")
            with source.open("rb") as stream:
                argv = ["ssh", "-T"] + session.options() + [session.destination,
                        "sh -c " + shlex.quote("umask 077; cat > " + quoted)]
                result = subprocess.run(argv, stdin=stream, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, timeout=timeout)
            if result.returncode:
                raise ToolError("SSH upload failed: " + result.stderr.decode("utf-8", "replace"))
        elif method == "http":
            config = profile.get("transfer", {})
            if not config.get("bind_address") and not profile["connection"].get("host"):
                raise ToolError("HTTP upload needs a reachable host bind_address or target network address")
            address = config.get("bind_address") or source_address(profile["connection"]["host"])
            with serve_one_file(source, address) as url:
                session.execute("umask 077; if command -v curl >/dev/null; then "
                                "curl -f --connect-timeout 5 --max-time {t} -o {dest} {url}; "
                                "else wget -T {t} -O {dest} {url}; fi".format(
                                    t=timeout, dest=quoted, url=shlex.quote(url)), timeout=timeout + 5)
        else:
            raise ToolError("unknown transfer method: " + method)
        _, output = session.execute("sha256sum " + quoted)
        if not output.split() or output.split()[0] != expected:
            raise ToolError("uploaded SHA256 does not match; destination was not replaced")
        mode = "700" if executable else "600"
        session.execute("chmod {mode} {tmp} && mv -f {tmp} {dest}".format(
            mode=mode, tmp=quoted, dest=shlex.quote(destination)))
    except (ToolError, OSError, subprocess.TimeoutExpired) as exc:
        # Preserve the failed partial path for diagnosis; never delete through a lost connection.
        raise ToolError("{}; upload staging path may remain: {}".format(exc, temporary)) from exc
    return {"source_sha256": expected, "size": source.stat().st_size,
            "destination": destination, "method": method}
