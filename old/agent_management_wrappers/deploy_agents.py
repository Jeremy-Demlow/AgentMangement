"""Compatibility wrapper for :mod:`agent_management.agents.deploy`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.deploy_agents` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.agents.deploy import *  # noqa: F401,F403
from agent_management.agents.deploy import main
from agent_management.agents import deploy as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
