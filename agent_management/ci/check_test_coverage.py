"""
Enforce dbt test coverage thresholds using fdbt.

Usage:
    python -m agent_management.ci.check_test_coverage --project dbt_ski_resort --threshold 70

Exit codes:
    0 = coverage meets threshold
    1 = coverage below threshold
"""
import argparse
import re
import subprocess
import sys
import os


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


def parse_coverage(output: str) -> dict:
    result = {}
    m = re.search(r"Models with tests:\s+(\d+)\s+\((\d+\.\d+)%\)", output)
    if m:
        result["model_count"] = int(m.group(1))
        result["model_pct"] = float(m.group(2))
    m = re.search(r"Total models:\s+(\d+)", output)
    if m:
        result["total_models"] = int(m.group(1))
    m = re.search(r"Models without tests:\s+(\d+)", output)
    if m:
        result["models_without_tests"] = int(m.group(1))
    m = re.search(r"Total tests:\s+(\d+)", output)
    if m:
        result["total_tests"] = int(m.group(1))
    return result


def main():
    parser = argparse.ArgumentParser(description="Check dbt test coverage threshold")
    parser.add_argument("--project", default="dbt_ski_resort", help="Path to dbt project")
    parser.add_argument("--threshold", type=float, default=70.0, help="Minimum model coverage %% (default: 70)")
    parser.add_argument("--layer", help="Filter by layer (staging, marts)")
    args = parser.parse_args()

    fdbt = find_fdbt()
    cmd = [fdbt, "-p", args.project, "tests", "coverage"]
    if args.layer:
        cmd.extend(["-l", args.layer])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    if result.returncode != 0:
        print(f"ERROR: fdbt failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    output = result.stdout
    stats = parse_coverage(output)

    pct = stats.get("model_pct", 0.0)
    total = stats.get("total_models", 0)
    tested = stats.get("model_count", 0)
    untested = stats.get("models_without_tests", 0)

    print(f"Coverage: {pct}% ({tested}/{total} models tested, {untested} untested)")
    print(f"Threshold: {args.threshold}%")

    if pct < args.threshold:
        print(f"FAIL: Coverage {pct}% is below threshold {args.threshold}%")
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"coverage_passed=false\n")
                f.write(f"coverage_pct={pct}\n")
        sys.exit(1)
    else:
        print(f"PASS: Coverage {pct}% meets threshold {args.threshold}%")
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"coverage_passed=true\n")
                f.write(f"coverage_pct={pct}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
