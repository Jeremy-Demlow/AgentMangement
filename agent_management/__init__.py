import logging

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("agent-management")
except PackageNotFoundError:
    __version__ = "0.6.0"

logger = logging.getLogger("agent_management")


def setup_logging(verbosity: int = 0) -> None:
    level = logging.WARNING if verbosity == 0 else logging.DEBUG if verbosity >= 2 else logging.INFO
    logging.basicConfig(
        format="%(message)s",
        level=level,
    )
    logger.setLevel(level)
