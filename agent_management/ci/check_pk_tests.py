"""
Validate that every dbt model has at least not_null + unique on its primary key.

Usage:
    python -m agent_management.ci.check_pk_tests --project dbt_ski_resort

Exit codes:
    0 = all models have PK tests
    1 = some models missing PK tests
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


SKIP_PATTERNS = [
    r"^sem_",
    r"^stg_customers$",
    r"^stg_locations$",
    r"^stg_lifts$",
    r"^stg_ticket_types$",
    r"^stg_products$",
]


def should_skip(model: str) -> bool:
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, model):
            return True
    return False


def parse_tests_list(output: str) -> dict[str, dict]:
    """Parse `fdbt tests list` output into {model: {has_unique, has_not_null}}."""
    models = {}
    current_model = None

    for line in output.splitlines():
        m = re.match(r"^Model:\s+(\S+)", line)
        if m:
            current_model = m.group(1)
            models[current_model] = {"has_unique": False, "has_not_null": False}
            continue

        if current_model and "Column-level tests:" in line:
            continue

        if current_model and line.strip().startswith("Model-level tests:"):
            continue

        if current_model and ":" in line and not line.strip().startswith("Path:") and not line.strip().startswith("Test definitions:"):
            parts = line.strip().split(":")
            if len(parts) == 2:
                tests_str = parts[1].strip().lower()
                if "unique" in tests_str:
                    models[current_model]["has_unique"] = True
                if "not_null" in tests_str:
                    models[current_model]["has_not_null"] = True

    return models


def main():
    parser = argparse.ArgumentParser(description="Check PK tests on all dbt models")
    parser.add_argument("--project", default="dbt_ski_resort", help="Path to dbt project")
    parser.add_argument("--strict", action="store_true", help="Fail if ANY model (including semantic views) lacks PK tests")
    args = parser.parse_args()

    fdbt = find_fdbt()

    cmd = [fdbt, "-p", args.project, "tests", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    if result.returncode != 0:
        print(f"ERROR: fdbt tests list failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    model_tests = parse_tests_list(result.stdout)

    cmd2 = [fdbt, "-p", args.project, "list", "-s"]
    result2 = subprocess.run(cmd2, capture_output=True, text=True, cwd=os.getcwd())
    all_model_names = set()
    for line in result2.stdout.splitlines():
        m = re.match(r"\s*\d+\.\s+(\w+)\s+\[", line)
        if m:
            all_model_names.add(m.group(1))

    skipped = []
    no_tests = []
    missing_pk = []

    for model in sorted(all_model_names):
        if not args.strict and should_skip(model):
            skipped.append(model)
            continue

        if model not in model_tests:
            no_tests.append(model)
            continue

        info = model_tests[model]
        missing = []
        if not info["has_unique"]:
            missing.append("unique")
        if not info["has_not_null"]:
            missing.append("not_null")
        if missing:
            missing_pk.append((model, missing))

    print("PK Test Validation Report")
    print("=" * 60)

    if skipped:
        print(f"\nSkipped ({len(skipped)} models):")
        for m in sorted(skipped):
            print(f"  - {m}")

    if no_tests:
        print(f"\nNo tests at all ({len(no_tests)} models):")
        for m in sorted(no_tests):
            print(f"  - {m}")

    if missing_pk:
        print(f"\nHave tests but missing PK coverage ({len(missing_pk)} models):")
        for m, missing in sorted(missing_pk):
            print(f"  - {m}: missing {', '.join(missing)}")

    total_issues = len(no_tests) + len(missing_pk)
    if total_issues == 0:
        print(f"\nPASS: All non-skipped models have PK tests (not_null + unique)")
        sys.exit(0)
    else:
        print(f"\nFAIL: {total_issues} models missing PK tests")
        sys.exit(1)


if __name__ == "__main__":
    main()
