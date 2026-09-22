import subprocess

from embedded_linux.transport import CommandError


class LocalShell:
    """Run real shell commands on disposable host fixtures, never on a device."""

    def execute(self, command, timeout=15, check=True, input_data=None):
        result = subprocess.run(["sh", "-c", command], input=input_data, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        text = result.stdout.decode("utf-8", "replace")
        if check and result.returncode:
            raise CommandError(result.returncode, text)
        return result.returncode, text

    def close(self):
        pass
