from __future__ import annotations

from anatomize.pack.formats import ContentEncoding, PackFile, PackFormat, PackPayload, PrefixStyle, render_prefix


def _payload(*, prefix_style: PrefixStyle) -> PackPayload:
    return PackPayload(
        root_name="repo",
        structure_paths=[],
        overview={"selected": {"files": 1, "python_files": 1, "binary_files": 0, "total_bytes": 10}},
        files=[PackFile(path="a.py", language="python", is_binary=False, content="print(1)\n")],
        encoding_name="cl100k_base",
        compressed=False,
        content_encoding=ContentEncoding.FENCE_SAFE,
        line_numbers=False,
        include_structure=False,
        include_files=False,
        prefix_style=prefix_style,
    )


def test_pack_prefix_markdown_standard_includes_guidance() -> None:
    text = render_prefix(_payload(prefix_style=PrefixStyle.STANDARD), fmt=PackFormat.MARKDOWN, include_structure=False)
    assert "# Code Pack" in text
    assert "## How to use" in text


def test_pack_prefix_markdown_minimal_omits_guidance() -> None:
    text = render_prefix(_payload(prefix_style=PrefixStyle.MINIMAL), fmt=PackFormat.MARKDOWN, include_structure=False)
    assert "# Code Pack" in text
    assert "## How to use" not in text


def test_pack_prefix_plain_standard_includes_notes() -> None:
    text = render_prefix(_payload(prefix_style=PrefixStyle.STANDARD), fmt=PackFormat.PLAIN, include_structure=False)
    assert "CODE_PACK" in text
    assert "NOTES:" in text


def test_pack_prefix_plain_minimal_omits_notes() -> None:
    text = render_prefix(_payload(prefix_style=PrefixStyle.MINIMAL), fmt=PackFormat.PLAIN, include_structure=False)
    assert "CODE_PACK" in text
    assert "NOTES:" not in text

