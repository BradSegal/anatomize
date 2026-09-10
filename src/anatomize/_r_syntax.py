"""Shared lexical boundaries for conservative R source inventory."""

from __future__ import annotations

import re

R_CALL_PATTERN = re.compile(r"(?<![\w.:$@])([A-Za-z.][\w.]*(?:::{1,2}[A-Za-z.][\w.]*)?)[ \t]*\(")
_RAW_OPEN = re.compile(r'[rR]"(-*)([([{])')


def r_code_mask(source: str, *, preserve_quoted: bool = False) -> str:
    """Blank comments and optionally quoted tokens, retaining offsets and newlines."""
    output = list(source)
    index = 0
    while index < len(source):
        character = source[index]
        end = index + 1
        raw = _RAW_OPEN.match(source, index) if character in "rR" else None
        if raw is not None and (index == 0 or not re.match(r"[\w.]", source[index - 1])):
            closing = {"(": ")", "[": "]", "{": "}"}[raw.group(2)] + raw.group(1) + '"'
            close = source.find(closing, raw.end())
            end = len(source) if close < 0 else close + len(closing)
        elif character == "#":
            close = source.find("\n", index)
            end = len(source) if close < 0 else close
        elif character in {'"', "'", "`"}:
            while end < len(source):
                if source[end] == "\\":
                    end += 2
                elif source[end] == character:
                    end += 1
                    break
                else:
                    end += 1
            end = min(end, len(source))
        else:
            index += 1
            continue
        if character == "#" or not preserve_quoted:
            for offset in range(index, end):
                if source[offset] not in "\r\n":
                    output[offset] = " "
        index = end
    return "".join(output)


def balanced_r_end(masked: str, start: int) -> int | None:
    """Find a matching closing delimiter in already-masked R source."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    for offset in range(start, len(masked)):
        character = masked[offset]
        if character in pairs:
            stack.append(pairs[character])
        elif character in ")]}":
            if not stack or stack.pop() != character:
                return None
            if not stack:
                return offset
    return None


def split_r_arguments(source: str) -> list[str]:
    """Split outer commas, retaining quoted and nested argument expressions."""
    masked = r_code_mask(source)
    result: list[str] = []
    start = 0
    index = 0
    while index < len(masked):
        if masked[index] in "([{":
            close = balanced_r_end(masked, index)
            if close is None:
                return []
            index = close
        elif masked[index] == ",":
            result.append(source[start:index].strip())
            start = index + 1
        index += 1
    result.append(source[start:].strip())
    return [clean for item in result if (clean := r_code_mask(item, preserve_quoted=True).strip())]
