"""Compression mode for `pack` (Python-only).

For `.py` files, this emits a deterministic structural summary using the
existing extractor at signature resolution.
"""

from __future__ import annotations

from pathlib import Path

from anatomize.core.extractor import SymbolExtractor
from anatomize.core.types import ClassInfo, FunctionInfo, ModuleInfo, ResolutionLevel


def compress_python_file(path: Path, *, module_name: str, relative_posix: str) -> str:
    """Compress a Python file to a structural stub representation.

    Extracts the module's structure at signature resolution and renders
    it as a minimal, syntactically valid Python stub.

    Parameters
    ----------
    path
        Absolute path to the Python file.
    module_name
        Fully qualified module name (e.g., 'pkg.sub.module').
    relative_posix
        Path relative to the source root (POSIX style).

    Returns
    -------
    str
        Compressed Python stub representation.
    """
    extractor = SymbolExtractor(resolution=ResolutionLevel.SIGNATURES)
    info = extractor.extract_module(path, module_name, relative_path=relative_posix, source=0)
    return render_module(info)


def render_module(info: ModuleInfo) -> str:
    """Render a ModuleInfo as a Python stub string.

    Produces a deterministic, minimal representation including:
    - Module docstring (if present)
    - Import statements
    - Module-level constants
    - Function stubs with signatures
    - Class stubs with attributes and method signatures

    Parameters
    ----------
    info
        Extracted module information.

    Returns
    -------
    str
        Python stub representation ending with a newline.
    """
    lines: list[str] = []
    if info.doc:
        lines.append(f'""" {info.doc} """')

    for imp in info.imports:
        lines.append(imp)

    if info.constants:
        lines.append("")
        for c in sorted(info.constants, key=lambda x: (x.line, x.name)):
            if c.annotation and c.default:
                lines.append(f"{c.name}: {c.annotation} = {c.default}")
            elif c.annotation:
                lines.append(f"{c.name}: {c.annotation}")
            elif c.default:
                lines.append(f"{c.name} = {c.default}")
            else:
                lines.append(c.name)

    for fn in sorted(info.functions, key=lambda f: (f.line, f.name)):
        lines.extend(_render_function(fn))

    for cls in sorted(info.classes, key=lambda c: (c.line, c.name)):
        lines.extend(_render_class(cls))

    return "\n".join(lines).rstrip() + "\n"


def _render_function(fn: FunctionInfo, *, indent: str = "") -> list[str]:
    out: list[str] = []
    out.append("")
    for dec in fn.decorators:
        out.append(f"{indent}@{dec}")
    prefix = "async " if fn.is_async else ""
    out.append(f"{indent}{prefix}def {fn.name}{fn.signature}: ...")
    return out


def _render_class(cls: ClassInfo) -> list[str]:
    out: list[str] = []
    out.append("")
    for dec in cls.decorators:
        out.append(f"@{dec}")
    bases = f"({', '.join(cls.bases)})" if cls.bases else ""
    out.append(f"class {cls.name}{bases}:")

    body: list[str] = []
    for a in sorted(cls.attributes, key=lambda x: (x.line, x.name)):
        if a.annotation and a.default:
            body.append(f"    {a.name}: {a.annotation} = {a.default}")
        elif a.annotation:
            body.append(f"    {a.name}: {a.annotation}")
        elif a.default:
            body.append(f"    {a.name} = {a.default}")
        else:
            body.append(f"    {a.name}")

    for m in sorted(cls.methods, key=lambda f: (f.line, f.name)):
        body.extend(_render_function(m, indent="    "))

    if not body:
        body.append("    ...")

    out.extend(body)
    return out
