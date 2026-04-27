import logging

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("agent-management")
except PackageNotFoundError:
    __version__ = "0.7.0"

logger = logging.getLogger("agent_management")


def setup_logging(verbosity: int = 0) -> None:
    level = logging.WARNING if verbosity == 0 else logging.DEBUG if verbosity >= 2 else logging.INFO
    logging.basicConfig(
        format="%(message)s",
        level=level,
    )
    logger.setLevel(level)


def __getattr__(name: str):
    # Lazy re-exports so importing the package stays cheap while giving users
    # the public API surface described in reqs/01_library_boundaries.md.
    _lazy = {
        "run_smoke_test": ("agent_management.smoke_test", "run_smoke_test"),
        "snapshot_agent": ("agent_management.snapshot_agent", "snapshot_agent"),
        "load_snapshot": ("agent_management.snapshot_agent", "load_snapshot"),
        "diff_snapshots": ("agent_management.snapshot_agent", "diff_snapshots"),
        "validate_spec_format": ("agent_management.validate_spec_format", "validate_spec_format"),
        "commit_version": ("agent_management.versioning", "commit_version"),
        "commit_live": ("agent_management.versioning", "commit_live"),
        "add_live_from_last": ("agent_management.versioning", "add_live_from_last"),
        "modify_live_spec": ("agent_management.versioning", "modify_live_spec"),
        "has_live_draft": ("agent_management.versioning", "has_live_draft"),
        "list_versions": ("agent_management.versioning", "list_versions"),
        "get_aliases": ("agent_management.versioning", "get_aliases"),
        "set_alias": ("agent_management.versioning", "set_alias"),
        "version_exists": ("agent_management.versioning", "version_exists"),
        "promote_alias": ("agent_management.versioning", "promote_alias"),
    }
    if name in _lazy:
        import importlib
        module_path, attr = _lazy[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module 'agent_management' has no attribute {name!r}")
