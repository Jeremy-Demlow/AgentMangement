"""Sync verified queries from YAML files into dbt semantic view models.

Reads verified_queries/*.yaml and merges verified_queries into the
WITH EXTENSION (CA=...) JSON block in each dbt sem_*.sql model.

Usage:
    python -m agent_management.sync_vqrs_to_dbt
    python -m agent_management.sync_vqrs_to_dbt --dry-run
    python -m agent_management.sync_vqrs_to_dbt --sv sem_revenue

Implements REQ-009: Semantic View Evaluation.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import yaml

from agent_management import setup_logging
from agent_management.paths import project_root

logger = logging.getLogger(__name__)

VQR_DIR = project_root() / "semantic-views" / "verified_queries"
DBT_SEMANTIC_DIR = project_root() / "dbt_ski_resort" / "models" / "marts" / "semantic"

CA_BLOCK_PATTERN = re.compile(
    r"(WITH\s+EXTENSION\s*\(\s*CA\s*=\s*\$\$)\s*(.*?)\s*(\$\$\s*\))",
    re.DOTALL | re.IGNORECASE,
)


def load_vqr_files(sv_filter: str | None = None) -> dict[str, list[dict]]:
    if not VQR_DIR.exists():
        logger.warning("VQR directory not found: %s", VQR_DIR)
        return {}

    results = {}
    for path in sorted(VQR_DIR.glob("*.yaml")):
        name = path.stem
        if sv_filter and name != sv_filter:
            continue
        with open(path) as f:
            data = yaml.safe_load(f)
        vqs = data.get("verified_queries", [])
        if vqs:
            results[name] = vqs
            logger.info("  Loaded %d VQRs from %s", len(vqs), path.name)
    return results


def vqrs_to_ca_json(vqrs: list[dict]) -> list[dict]:
    ca_vqrs = []
    for vq in vqrs:
        entry = {
            "name": vq["name"],
            "question": vq["question"],
            "sql": vq["sql"],
            "verified_by": vq.get("verified_by", "agent_management"),
            "verified_at": vq.get("verified_at", 0),
        }
        if "use_as_onboarding_question" in vq:
            entry["use_as_onboarding_question"] = vq["use_as_onboarding_question"]
        ca_vqrs.append(entry)
    return ca_vqrs


def inject_vqrs_into_model(sql_content: str, vqrs: list[dict]) -> str | None:
    match = CA_BLOCK_PATTERN.search(sql_content)
    if not match:
        return None

    prefix = match.group(1)
    json_body = match.group(2)
    suffix = match.group(3)

    try:
        ca_obj = json.loads(json_body)
    except json.JSONDecodeError:
        logger.error("    Failed to parse existing CA JSON")
        return None

    ca_obj["verified_queries"] = vqrs_to_ca_json(vqrs)
    new_json = json.dumps(ca_obj, indent=2)
    new_block = f"{prefix}\n{new_json}\n{suffix}"

    return sql_content[:match.start()] + new_block + sql_content[match.end():]


def sync(sv_filter: str | None = None, dry_run: bool = False) -> int:
    vqr_map = load_vqr_files(sv_filter)
    if not vqr_map:
        logger.warning("No VQR files found")
        return 0

    synced = 0
    for sv_name, vqrs in vqr_map.items():
        model_path = DBT_SEMANTIC_DIR / f"{sv_name}.sql"
        if not model_path.exists():
            logger.warning("  dbt model not found: %s", model_path.name)
            continue

        logger.info("\n  Syncing %s (%d VQRs) -> %s", sv_name, len(vqrs), model_path.name)
        sql_content = model_path.read_text()
        updated = inject_vqrs_into_model(sql_content, vqrs)

        if updated is None:
            logger.error("    No WITH EXTENSION (CA=...) block found in %s", model_path.name)
            continue

        if updated == sql_content:
            logger.info("    No changes needed")
            continue

        if dry_run:
            logger.info("    [DRY RUN] Would update %s", model_path.name)
        else:
            model_path.write_text(updated)
            logger.info("    Updated %s", model_path.name)

        synced += 1

    return synced


def main():
    parser = argparse.ArgumentParser(description="Sync VQRs into dbt semantic view models")
    parser.add_argument("--sv", help="Sync a single semantic view by name (e.g. sem_revenue)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger.info("Syncing verified queries into dbt models...")

    count = sync(sv_filter=args.sv, dry_run=args.dry_run)
    logger.info("\n%d model(s) %s", count, "would be updated" if args.dry_run else "updated")

    if count == 0 and args.sv:
        logger.warning("No VQR file found for '%s' in %s", args.sv, VQR_DIR)
        sys.exit(1)


if __name__ == "__main__":
    main()
