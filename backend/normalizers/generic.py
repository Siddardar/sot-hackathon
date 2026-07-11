"""Normalizer for the generic transcript format.

Accepts several shapes, in order of how common they are:

  * A flat list of messages:
        [{"role": "user"|"assistant", "content": "..."}, ...]
  * A single conversation object:
        {"title": "...", "messages": [{"role", "content"}, ...]}
  * A list of conversation objects (each with a ``messages`` array).

Roles other than ``user`` are treated as ``assistant`` so exotic exports still
load. Message ids are taken from the payload when present, otherwise generated.
"""

from __future__ import annotations

from typing import Any

from schemas import Conversation, Message


def _is_message(obj: Any) -> bool:
    return isinstance(obj, dict) and "content" in obj and "role" in obj


def looks_like_generic(data: Any) -> bool:
    if isinstance(data, list):
        if not data:
            return False
        first = data[0]
        if _is_message(first):
            return True
        if isinstance(first, dict) and isinstance(first.get("messages"), list):
            return True
        return False
    if isinstance(data, dict):
        return isinstance(data.get("messages"), list)
    return False


def _normalize_role(role: Any) -> str:
    return "user" if role == "user" else "assistant"


def _content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    # Some payloads use a list of {type: "text", text: "..."} blocks.
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                chunks.append(block["text"])
        return "\n".join(c for c in chunks if c).strip()
    return ""


def _normalize_messages(raw_messages: list, offset: int = 0) -> list[Message]:
    messages: list[Message] = []
    for i, raw in enumerate(raw_messages):
        if not isinstance(raw, dict):
            continue
        content = _content_to_str(raw.get("content"))
        if not content:
            continue
        message_id = str(raw.get("id") or f"m{offset + i}")
        messages.append(
            Message(
                id=message_id,
                role=_normalize_role(raw.get("role")),
                content=content,
                timestamp=raw.get("timestamp") or raw.get("create_time"),
            )
        )
    return messages


def _normalize_conversation(conv: dict, index: int) -> Conversation:
    conversation_id = str(conv.get("conversation_id") or conv.get("id") or f"conversation-{index}")
    title = (conv.get("title") or conv.get("name") or "Conversation").strip() or "Conversation"
    messages = _normalize_messages(conv.get("messages") or [])
    return Conversation(conversation_id=conversation_id, title=title, messages=messages)


def normalize(data: Any) -> list[Conversation]:
    # Case 1: a flat list of message dicts -> a single conversation.
    if isinstance(data, list) and data and _is_message(data[0]):
        messages = _normalize_messages(data)
        if not messages:
            return []
        return [Conversation(conversation_id="conversation-0", title="Conversation", messages=messages)]

    # Case 2: a list of conversation objects.
    if isinstance(data, list):
        result: list[Conversation] = []
        for index, conv in enumerate(data):
            if isinstance(conv, dict) and isinstance(conv.get("messages"), list):
                normalized = _normalize_conversation(conv, index)
                if normalized.messages:
                    result.append(normalized)
        return result

    # Case 3: a single conversation object.
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        normalized = _normalize_conversation(data, 0)
        return [normalized] if normalized.messages else []

    return []
