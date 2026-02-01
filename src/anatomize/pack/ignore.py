"""Ignore pattern loading for `pack`.

This intentionally uses the same gitignore-like matcher as the generator
(`anatomize.core.exclude.Excluder`) to keep behavior consistent and
predictable.
"""

from __future__ import annotations

from pathlib import Path

from anatomize.core.exclude import Excluder, IgnorePattern

DEFAULT_IGNORE_PATTERNS: list[str] = [
    "__pycache__/",
    "*.pyc",
    "*.log",
    "*.log.*",
    "*.tmp",
    "*.bak",
    ".git/",
    ".venv/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".anatomy/",
    ".runtime/",
    ".tox/",
    "dist/",
    "build/",
    "*.egg-info/",
    ".DS_Store",
    "Thumbs.db",
]


STANDARD_IGNORE_FILES: list[str] = [
    ".repomixignore",
    ".ignore",
    ".gitignore",
    ".git/info/exclude",
]


def build_excluder(
    root: Path, *, ignore: list[str], ignore_files: list[Path], respect_standard_ignores: bool
) -> Excluder:
    """Build an Excluder from multiple pattern sources.

    Combines default patterns, standard ignore files (gitignore, etc.),
    custom ignore files, and CLI-provided patterns into a single Excluder.

    Parameters
    ----------
    root
        Root directory for resolving standard ignore file paths.
    ignore
        CLI-provided ignore patterns.
    ignore_files
        Paths to additional ignore files.
    respect_standard_ignores
        If True, load .gitignore and similar standard files.

    Returns
    -------
    Excluder
        Configured excluder instance.
    """
    patterns: list[IgnorePattern] = []
    patterns.extend((p, "default") for p in DEFAULT_IGNORE_PATTERNS)

    if respect_standard_ignores:
        for rel in STANDARD_IGNORE_FILES:
            p = root / rel
            if p.exists() and p.is_file():
                patterns.extend((line, f"standard_ignore_file:{rel}") for line in _read_patterns_file(p))

    for p in ignore_files:
        patterns.extend((line, f"ignore_file:{p}") for line in _read_patterns_file(p))

    patterns.extend((line, "cli") for line in ignore)
    return Excluder(patterns)


def _read_patterns_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read ignore file: {path}") from e
    return [line.rstrip("\n") for line in text.splitlines()]
