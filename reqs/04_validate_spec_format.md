# 04 — agent_management.validate_spec_format

## Problem

`tests/test_templates.py::TestToolDescriptionFormat` enforces the PURPOSE/DATA/KEY METRICS/KEY DIMENSIONS/USE FOR/NOT FOR/CROSS-REFERENCE WITH template and rejects hardcoded season strings. The logic is trapped in a pytest file — it can't be called from a pre-commit hook, a `snowflake-cli` plugin, or a library consumer who wants to validate a draft spec before committing.

## Goal

Extract the validation logic into `agent_management/validate_spec_format.py`:

```python
def validate_spec_format(spec_path: Path | str) -> list[ValidationError]:
    """Returns empty list on success; each error has field, rule, message."""

@dataclass
class ValidationError:
    path: str        # e.g. "tools[0].description"
    rule: str        # e.g. "template_section_missing:DATA"
    message: str
```

Rules enforced:

1. `template_section_present` — all 7 sections present in every tool description
2. `template_section_order` — sections appear in canonical order
3. `no_hardcoded_seasons` — no literal "2024-2025 season" etc in descriptions (use metric definitions instead)
4. `agent_version_bump_on_spec_change` — version string in spec matches rules (minor for additive, major for breaking)
5. `fqn_matches_env` — agent FQN in spec matches the env being deployed to

## CLI

```
python -m agent_management.validate_spec_format agents/specs/resort_executive.yml
# exit 0 if valid, exit 1 with error table if not
```

## Test file rewrite

`tests/test_templates.py::TestToolDescriptionFormat` becomes:

```python
def test_resort_executive_format():
    errs = validate_spec_format("agents/specs/resort_executive.yml")
    assert errs == []
```

All the rule logic moves to the library; the test is a thin assertion.

## Pre-commit hook (optional, follow-up)

```yaml
- id: validate-agent-specs
  name: Validate agent spec format
  entry: python -m agent_management.validate_spec_format
  language: system
  files: ^agents/specs/.*\.yml$
```
