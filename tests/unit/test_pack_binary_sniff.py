from __future__ import annotations

from pathlib import Path

import pytest

from anatomize.pack.discovery import _is_binary_file

pytestmark = pytest.mark.unit


def test_binary_sniff_reads_only_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "big.txt"
    p.write_text("a" * 50_000, encoding="utf-8")

    read_sizes: list[int] = []
    orig_open = Path.open

    def open_wrapper(self: Path, mode: str = "r", *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        f = orig_open(self, mode, *args, **kwargs)
        if self == p and "b" in mode:
            class _Wrapped:
                def __init__(self, inner):  # type: ignore[no-untyped-def]
                    self._inner = inner

                def read(self, n: int = -1) -> bytes:
                    read_sizes.append(n)
                    return self._inner.read(n)

                def __enter__(self):  # type: ignore[no-untyped-def]
                    self._inner.__enter__()
                    return self

                def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                    return self._inner.__exit__(exc_type, exc, tb)

                def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
                    return getattr(self._inner, name)

            return _Wrapped(f)
        return f

    monkeypatch.setattr(Path, "open", open_wrapper)

    _is_binary_file(p, sniff_bytes=8)
    assert read_sizes == [8]

