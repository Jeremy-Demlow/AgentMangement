"""Validate agent spec format against the library's contract.

Extracted from tests/test_templates.py::TestToolDescriptionFormat so the rules
are callable from pre-commit hooks, CI, and ad-hoc spec review.

Rules enforced:

  R1  template_section_present  — every tool description contains the 7 canonical
      sections (PURPOSE, DATA, KEY METRICS, KEY DIMENSIONS, USE FOR, NOT FOR,
      CROSS-REFERENCE WITH).
  R2  template_section_order    — sections appear in canonical order.
  R3  no_hardcoded_seasons      — instructions blocks do not contain literal
      season strings like '2024-2025'; seasons must be resolved via DIM_DATE.

Usage::

    from agent_management.validate_spec_format import validate_spec_format
    errors = validate_spec_format("agents/specs/resort_executive.yml")

CLI::

    python -m agent_management.validate_spec_format agents/specs/*.yml
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import yaml

from agent_management.render_template import render_file
from agent_management.utils.config import load_env_config


REQUIRED_SECTIONS: tuple[str, ...] = (
    "PURPOSE:",
    "DATA:",
    "KEY METRICS",
    "KEY DIMENSIONS",
    "USE FOR:",
    "NOT FOR:",
    "CROSS-REFERENCE WITH:",
)

_SEASON_PATTERN = re.compile(r"\b20\d{2}-20?\d{2}\b")


@dataclass(frozen=True)
class ValidationError:
    path: str
    rule: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.rule}] {self.path}: {self.message}"


def _iter_tools(spec: dict) -> Iterable[tuple[int, dict]]:
    for idx, tool in enumerate(spec.get("tools", [])):
        yield idx, tool or {}


def _check_sections(spec_path: str, spec: dict) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for idx, tool in _iter_tools(spec):
        name = tool.get("name", f"<tool#{idx}>")
        description = tool.get("description", "") or ""
        where = f"{spec_path}::tools[{idx}]({name})"

        # R1: required sections present
        missing = [s for s in REQUIRED_SECTIONS if s not in description]
        for section in missing:
            errors.append(
                ValidationError(
                    path=where,
                    rule="template_section_missing",
                    message=f"missing required section '{section}'",
                )
            )

        # R2: canonical order — only checked when all sections present
        if not missing:
            positions = [description.index(s) for s in REQUIRED_SECTIONS]
            if positions != sorted(positions):
                errors.append(
                    ValidationError(
                        path=where,
                        rule="template_section_order",
                        message=(
                            "sections out of canonical order; expected "
                            + " -> ".join(REQUIRED_SECTIONS)
                        ),
                    )
                )
    return errors


def _check_no_hardcoded_seasons(spec_path: str, spec: dict) -> list[ValidationError]:
    instructions = spec.get("instructions") or {}
    orchestration = instructions.get("orchestration", "") or ""
    response = instructions.get("response", "") or ""
    combined = f"{orchestration}\n{response}"
    found = _SEASON_PATTERN.findall(combined)
    if not found:
        return []
    return [
        ValidationError(
            path=f"{spec_path}::instructions",
            rule="no_hardcoded_seasons",
            message=(
                f"hardcoded season strings {sorted(set(found))}; resolve seasons "
                "dynamically via DIM_DATE (see docs/operations/AGENT_VERSIONING.md)"
            ),
        )
    ]


def validate_spec_format(
    spec_path: Path | str,
    *,
    env: str = "dev",
) -> list[ValidationError]:
    """Validate a single agent spec file.

    Renders the Jinja template against ``env`` config (defaults to dev) and
    checks the resulting YAML against the format rules. Returns an empty list
    when the spec is valid.
    """
    spec_path = str(spec_path)
    config = load_env_config(env)
    rendered = render_file(spec_path, config)
    spec = yaml.safe_load(rendered) or {}
    errors: list[ValidationError] = []
    errors.extend(_check_sections(spec_path, spec))
    errors.extend(_check_no_hardcoded_seasons(spec_path, spec))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate agent spec format.")
    parser.add_argument(
        "paths",
        nargs="+",
        help="One or more spec YAML paths (globs are expanded by the shell).",
    )
    parser.add_argument(
        "--env",
        default="dev",
        help="Environment to render templates against (default: dev).",
    )
    args = parser.parse_args(argv)

    all_errors: list[ValidationError] = []
    for spec in args.paths:
        all_errors.extend(validate_spec_format(spec, env=args.env))

    if not all_errors:
        print(f"OK: {len(args.paths)} spec(s) valid.")
        return 0

    print(f"FAIL: {len(all_errors)} validation error(s):", file=sys.stderr)
    for err in all_errors:
        print(f"  {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
