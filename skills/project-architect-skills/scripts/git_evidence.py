"""Run a local read-only Git query and preserve its byte-oriented output."""

import os
import subprocess


def git(*arguments):
    # Partial clones can otherwise fetch objects during diff or rename detection.
    environment = {**os.environ, "GIT_ALLOW_PROTOCOL": "", "GIT_OPTIONAL_LOCKS": "0"}
    result = subprocess.run(["git", "--no-pager", *arguments], capture_output=True, env=environment)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip() or "Git 命令失败")
    return result.stdout
