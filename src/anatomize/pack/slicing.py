"""Selection modes for `pack`."""

from __future__ import annotations

from enum import Enum


class SliceBackend(str, Enum):
    """Backend for dependency/usage slicing.

    Attributes
    ----------
    IMPORTS
        Static import analysis (fast, no external tools).
    PYRIGHT
        Pyright language server for precise cross-references.
    """

    IMPORTS = "imports"
    PYRIGHT = "pyright"
