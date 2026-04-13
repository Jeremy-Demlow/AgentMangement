import os
import subprocess
import sys


def find_fdbt() -> str:
    fdbt = os.environ.get("FDBT_PATH")
    if fdbt and os.path.isfile(fdbt):
        return fdbt
    result = subprocess.run(["which", "fdbt"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    cortex_dir = os.path.expanduser("~/.local/share/cortex")
    if os.path.isdir(cortex_dir):
        candidates = []
        for d in os.listdir(cortex_dir):
            p = os.path.join(cortex_dir, d, "fdbt")
            if os.path.isfile(p):
                candidates.append(p)
        if candidates:
            return sorted(candidates)[-1]
    print("ERROR: fdbt not found. Set FDBT_PATH or install fdbt.", file=sys.stderr)
    sys.exit(1)
