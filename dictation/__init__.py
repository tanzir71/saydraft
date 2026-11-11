"""Compatibility imports for the moved ``saydraft.dictation`` package."""

from __future__ import annotations

import importlib
import sys

_PACKAGE = importlib.import_module("saydraft.dictation")
_SUBMODULES = (
    "glossary",
    "llm_local",
    "pipeline",
    "protect",
    "rules",
    "types",
    "validation",
)

for _name in getattr(_PACKAGE, "__all__", ()):
    globals()[_name] = getattr(_PACKAGE, _name)

for _submodule in _SUBMODULES:
    sys.modules[f"{__name__}.{_submodule}"] = importlib.import_module(
        f"saydraft.dictation.{_submodule}"
    )

__all__ = list(getattr(_PACKAGE, "__all__", ()))
