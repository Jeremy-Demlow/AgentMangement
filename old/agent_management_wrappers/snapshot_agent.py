"""Compatibility wrapper for :mod:`agent_management.agents.snapshot`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.snapshot_agent` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.agents.snapshot import *  # noqa: F401,F403
from agent_management.agents.snapshot import main
from agent_management.agents import snapshot as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
