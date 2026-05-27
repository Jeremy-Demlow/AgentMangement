"""Bootstrap or reconcile GitHub Environments from a snapshot file.

Reads examples/github-environments-snapshot.json by default and:
  - Creates the environment if it doesn't exist
  - Sets required reviewers per snapshot
  - Sets environment variables per snapshot
  - Does NOT set secrets (those must be done manually via GH UI or a separate
    secure flow - this script only handles non-sensitive config)

Usage:
    python scripts/bootstrap_gh_environments.py --repo Jeremy-Demlow/AgentMangement

    # Dry-run (no writes):
    python scripts/bootstrap_gh_environments.py --repo ... --dry-run

    # Only specific env:
    python scripts/bootstrap_gh_environments.py --repo ... --only PROD

Requires: gh CLI authenticated with repo:admin scope.

Implements REQ-030: GitHub Environments as code (via snapshot + reconcile).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "examples" / "github-environments-snapshot.json"


def gh(*args, check=True, capture=True):
    """Run gh CLI and return stdout."""
    result = subprocess.run(
        ["gh"] + list(args),
        capture_output=capture, text=True,
    )
    if check and result.returncode != 0:
        print(f"gh command failed: gh {' '.join(args)}")
        print(result.stderr)
        sys.exit(result.returncode)
    return result


def lookup_user_id(login: str) -> int:
    """Resolve a GitHub username to a numeric user ID via gh api."""
    result = gh("api", f"/users/{login}", capture=True)
    return json.loads(result.stdout)["id"]


def ensure_environment(repo: str, env_name: str, spec: dict, dry_run: bool):
    """Create or update a GitHub environment matching spec."""
    print(f"\n=== {env_name} ===")

    # Build reviewers payload (users only; team support would be similar)
    reviewers_payload = []
    for rv in spec.get("reviewers", []):
        if rv["type"] == "User":
            login = rv["login"]
            uid = lookup_user_id(login)
            reviewers_payload.append({"type": "User", "id": uid})
            print(f"  reviewer: {login} (id={uid})")
        else:
            print(f"  WARNING: unsupported reviewer type: {rv}")

    env_body = {"reviewers": reviewers_payload}
    print(f"  body: {env_body}")

    if dry_run:
        print(f"  [dry-run] would PUT /repos/{repo}/environments/{env_name}")
    else:
        # PUT creates-or-updates
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(env_body, f)
            body_file = f.name
        gh("api", "--method", "PUT",
           f"/repos/{repo}/environments/{env_name}",
           "--input", body_file)
        print(f"  env upserted")

    # Variables
    for name, value in (spec.get("variables") or {}).items():
        if dry_run:
            print(f"  [dry-run] would set var {name}={value}")
        else:
            # Try update first, create if not found
            r = gh("api", "--method", "PATCH",
                   f"/repos/{repo}/environments/{env_name}/variables/{name}",
                   "-f", f"name={name}", "-f", f"value={value}",
                   check=False)
            if r.returncode != 0:
                gh("api", "--method", "POST",
                   f"/repos/{repo}/environments/{env_name}/variables",
                   "-f", f"name={name}", "-f", f"value={value}")
            print(f"  var {name} set")

    secrets = spec.get("secrets") or []
    if secrets:
        print(f"  NOTE: {len(secrets)} secret name(s) in snapshot — NOT set by this script:")
        for s in secrets:
            print(f"    - {s}  (set manually via gh secret set or UI)")


def validate_required_secrets(repo: str, required: list[str]) -> list[str]:
    """Return list of missing required secrets. Does NOT read secret values
    (gh CLI only exposes NAMES for security), only verifies existence."""
    result = gh("api", f"/repos/{repo}/actions/secrets", capture=True)
    present = {s["name"] for s in json.loads(result.stdout).get("secrets", [])}
    return [name for name in required if name not in present]


def main():
    ap = argparse.ArgumentParser(description="Bootstrap GitHub Environments from snapshot")
    ap.add_argument("--repo", required=True, help="owner/name (e.g. Jeremy-Demlow/AgentMangement)")
    ap.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH,
                    help=f"Path to snapshot JSON (default: {SNAPSHOT_PATH})")
    ap.add_argument("--only", help="Only process this env name (e.g. PROD)")
    ap.add_argument("--skip", action="append", default=[], help="Env name to skip (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    ap.add_argument("--check-secrets", action="store_true",
                    help="Also check required repo-level secrets exist; fails if any missing")
    args = ap.parse_args()

    if not args.snapshot.exists():
        print(f"Snapshot not found: {args.snapshot}")
        sys.exit(1)

    data = json.loads(args.snapshot.read_text())
    envs = data.get("envs", {})
    if not envs:
        print("No envs in snapshot"); sys.exit(1)

    print(f"Repo: {args.repo}")
    print(f"Snapshot: {args.snapshot}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Envs in snapshot: {list(envs.keys())}")

    if args.check_secrets:
        required = data.get("required_repo_secrets", [])
        if required:
            print(f"\n=== Required repo secrets: {required} ===")
            missing = validate_required_secrets(args.repo, required)
            if missing:
                print(f"MISSING SECRETS: {missing}")
                print("Set them with: gh secret set <NAME> --body '<VALUE>'")
                sys.exit(2)
            print("All required secrets present.")

    for env_name, spec in envs.items():
        if args.only and env_name != args.only:
            continue
        if env_name in args.skip:
            print(f"\n=== {env_name} SKIPPED ===")
            continue
        ensure_environment(args.repo, env_name, spec, args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
