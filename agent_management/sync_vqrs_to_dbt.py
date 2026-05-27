"""Compatibility wrapper for :mod:`agent_management.semantic_views.vqrs`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.sync_vqrs_to_dbt` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.semantic_views.vqrs import *  # noqa: F401,F403
from agent_management.semantic_views.vqrs import main
from agent_management.semantic_views import vqrs as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
