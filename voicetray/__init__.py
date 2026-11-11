"""Deprecated package name, retained for one release."""

import logging

from saydraft import __version__

__all__ = ["__version__"]

logging.getLogger("saydraft.compat").warning(
    "VoiceTray is now Saydraft; use python -m saydraft."
)
