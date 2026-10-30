#!/usr/bin/env python3
"""Existing build, stage, package and test entrypoints for the sample project."""

import argparse
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*argv):
    subprocess.run(argv, cwd=str(ROOT), check=True, timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "stage", "package", "test"))
    args = parser.parse_args()
    (ROOT / "output").mkdir(exist_ok=True)
    with (ROOT / "output/actions.jsonl").open("a") as stream:
        stream.write(json.dumps({"action": args.action}) + "\n")
    if args.action == "build":
        (ROOT / "build").mkdir(exist_ok=True)
        run("gcc", "-Wall", "-Wextra", "-O2", "-fPIC", "-shared", "-Isrc",
            "src/sensor.c", "-o", "build/libsample.so")
        run("gcc", "-Wall", "-Wextra", "-O2", "-Isrc", "src/main.c", "-Lbuild",
            "-lsample", "-Wl,-rpath,$ORIGIN/../lib", "-o", "build/sample")
    elif args.action == "stage":
        for folder, name in (("lib", "libsample.so"), ("bin", "sample")):
            destination = ROOT / "stage" / folder
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(ROOT / "build" / name), str(destination / name))
    elif args.action == "package":
        config = json.loads((ROOT / "package.json").read_text())
        with tarfile.open(str(ROOT / "output/application.tar"), "w") as archive:
            for source, name in ((config["library"], "lib/libsample.so"),
                                 ("stage/bin/sample", "bin/sample")):
                info = archive.gettarinfo(str(ROOT / source), arcname=name)
                info.mtime = info.uid = info.gid = 0
                info.uname = info.gname = ""
                with (ROOT / source).open("rb") as stream:
                    archive.addfile(info, stream)
    else:
        suite = json.loads((ROOT / "tests/suite.json").read_text())
        if not suite:
            raise SystemExit("no test cases selected")
        for name, sources in suite.items():
            executable = "output/test-" + name
            run("gcc", "-Wall", "-Wextra", "-Isrc", *sources, "-o", executable)
            run("./" + executable)
        print("{} test case(s) passed".format(len(suite)))


if __name__ == "__main__":
    main()
