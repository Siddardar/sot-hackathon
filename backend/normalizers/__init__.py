"""Normalizer dispatch: turn any supported upload into canonical conversations.

Supported formats:
  * ``claude``  — Claude ``conversations.json`` export
  * ``chatgpt`` — ChatGPT ``conversations.json`` export
  * ``generic`` — simple ``[{"role", "content"}]`` arrays / conversation objects

Use :func:`normalize` with ``fmt="auto"`` to detect the format, or pass an
explicit format string.
"""

from __future__ import annotations

from typing import Any

from schemas import Conversation

from . import chatgpt, claude, generic


class UnsupportedFormatError(ValueError):
    """Raised when an upload does not match any known format."""


def detect_format(data: Any) -> str:
    """Return the best-guess format name for a parsed JSON payload."""
    # Order matters: Claude and ChatGPT have distinctive keys; generic is the
    # catch-all and is checked last.
    if claude.looks_like_claude(data):
        return "claude"
    if chatgpt.looks_like_chatgpt(data):
        return "chatgpt"
    if generic.looks_like_generic(data):
        return "generic"
    raise UnsupportedFormatError(
        "Could not detect the transcript format. Expected a Claude export, "
        "a ChatGPT export, or a generic [{'role', 'content'}] array."
    )


_NORMALIZERS = {
    "claude": claude.normalize,
    "chatgpt": chatgpt.normalize,
    "generic": generic.normalize,
}


def normalize(data: Any, fmt: str = "auto") -> tuple[str, list[Conversation]]:
    """Normalize ``data`` into canonical conversations.

    Returns a ``(format, conversations)`` tuple so callers can report which
    format was actually used (useful when ``fmt="auto"``).
    """
    fmt = (fmt or "auto").lower()
    if fmt == "auto":
        fmt = detect_format(data)

    normalizer = _NORMALIZERS.get(fmt)
    if normalizer is None:
        raise UnsupportedFormatError(f"Unknown format '{fmt}'. Expected one of {sorted(_NORMALIZERS)}.")

    conversations = normalizer(data)
    if not conversations:
        raise UnsupportedFormatError(
            f"No conversations with messages were found for format '{fmt}'."
        )
    return fmt, conversations


__all__ = ["normalize", "detect_format", "UnsupportedFormatError"]
