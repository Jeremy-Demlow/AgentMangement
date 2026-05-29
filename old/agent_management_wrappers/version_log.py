"""Compatibility wrapper for :mod:`agent_management.agents.version_log`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.version_log` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.agents.version_log import *  # noqa: F401,F403
from agent_management.agents.version_log import main
from agent_management.agents import version_log as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
