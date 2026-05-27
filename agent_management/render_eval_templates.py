"""Compatibility wrapper for :mod:`agent_management.evals.render_templates`.

The implementation moved into a domain package. This module remains so
`python -m agent_management.render_eval_templates` and historical imports keep working.
"""
from __future__ import annotations

from agent_management.evals.render_templates import *  # noqa: F401,F403
from agent_management.evals.render_templates import main
from agent_management.evals import render_templates as _impl


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
