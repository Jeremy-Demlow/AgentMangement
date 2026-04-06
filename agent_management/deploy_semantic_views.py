"""Deploy semantic view YAMLs to Snowflake.

Renders Jinja2 templates with environment config, then deploys via
SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML.

Usage:
    python -m agent_management.deploy_semantic_views --env dev
    python -m agent_management.deploy_semantic_views --env dev --view sem_revenue
    python -m agent_management.deploy_semantic_views --env dev --dry-run

Implements REQ-002: Semantic View CI/CD Pipeline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_management.render_template import render_file
from agent_management.utils.config import get_semantic_schema, load_env_config
from agent_management.utils.snowflake_client import connect

DEFINITIONS_DIR = Path(__file__).resolve().parent.parent / "semantic-views" / "definitions"


def find_sv_files(view: str | None) -> list[Path]:
    if view:
        path = DEFINITIONS_DIR / f"{view}.yml"
        if not path.exists():
            path = DEFINITIONS_DIR / f"{view}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Semantic view YAML not found: {view}")
        return [path]
    files = sorted(DEFINITIONS_DIR.glob("sem_*.y*ml"))
    if not files:
        print(f"No semantic view YAMLs found in {DEFINITIONS_DIR}")
        sys.exit(0)
    return files


def deploy_one(cur, schema_fqn: str, yaml_content: str, name: str, dry_run: bool) -> bool:
    if "$$" in yaml_content:
        print(f"  {name}... SKIPPED — YAML contains '$$'")
        return False

    if dry_run:
        print(f"  [DRY RUN] {name} — validating...")
        try:
            cur.execute(
                f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{schema_fqn}', $${yaml_content}$$, TRUE)"
            )
            result = cur.fetchone()
            print(f"  {name}... VALID — {result[0] if result else 'ok'}")
            return True
        except Exception as e:
            print(f"  {name}... INVALID — {e}")
            return False

    print(f"  Deploying {name}...", end=" ", flush=True)
    try:
        cur.execute(
            f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{schema_fqn}', $${yaml_content}$$, FALSE)"
        )
        result = cur.fetchone()
        print(f"OK — {result[0] if result else 'deployed'}")
        return True
    except Exception as e:
        print(f"FAILED — {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Deploy semantic views from YAML")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--view", "-v", help="Deploy single view by name")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Validate only, no deploy")
    args = parser.parse_args()

    config = load_env_config(args.env)
    schema_fqn = get_semantic_schema(config)
    sv_files = find_sv_files(args.view)

    print(f"Environment: {config['environment']}")
    print(f"Target: {schema_fqn}")
    print(f"Views: {len(sv_files)}")
    print("=" * 60)

    conn = connect(config, schema=config["deployment"]["semantic_schema"])
    cur = conn.cursor()

    success = 0
    failed = 0
    for path in sv_files:
        name = path.stem
        rendered = render_file(path, config)
        if deploy_one(cur, schema_fqn, rendered, name, args.dry_run):
            success += 1
        else:
            failed += 1

    print(f"\n{'=' * 60}")
    action = "Validated" if args.dry_run else "Deployed"
    print(f"{action}: {success}  Failed: {failed}  Environment: {config['environment']}")

    if not args.dry_run:
        cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {schema_fqn}")
        rows = cur.fetchall()
        print(f"\nSemantic views in {schema_fqn}: {len(rows)}")
        for row in rows:
            print(f"  - {row[1]}")

    cur.close()
    conn.close()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
