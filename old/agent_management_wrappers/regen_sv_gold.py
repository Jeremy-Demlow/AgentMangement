"""Compatibility wrapper for :mod:`agent_management.semantic_views.regen_gold`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.regen_sv_gold` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.semantic_views.regen_gold import *  # noqa: F401,F403
from agent_management.semantic_views.regen_gold import main
from agent_management.semantic_views import regen_gold as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
