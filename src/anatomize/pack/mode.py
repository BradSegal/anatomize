"""Pack mode selection."""

from __future__ import annotations

from enum import Enum


class PackMode(str, Enum):
    """Pack output mode.

    Attributes
    ----------
    BUNDLE
        All files rendered with full content.
    HYBRID
        Files rendered with content, summary, or meta based on rules.
    """

    BUNDLE = "bundle"
    HYBRID = "hybrid"
