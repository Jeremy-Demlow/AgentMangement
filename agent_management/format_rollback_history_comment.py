"""Compatibility wrapper for :mod:`agent_management.evals.rollback_comment`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.format_rollback_history_comment` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.evals.rollback_comment import *  # noqa: F401,F403
from agent_management.evals.rollback_comment import main
from agent_management.evals import rollback_comment as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
