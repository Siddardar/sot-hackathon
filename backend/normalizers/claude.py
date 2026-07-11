"""Normalizer for Claude data exports (``conversations.json``).

Claude exports are a JSON array of conversation objects, each shaped roughly:

    {
      "uuid": "...",
      "name": "Weekend trip planning",
      "created_at": "...",
      "chat_messages": [
        {"uuid": "...", "sender": "human"|"assistant",
         "text": "...", "content": [{"type": "text", "text": "..."}],
         "created_at": "..."}
      ]
    }

We also accept a single conversation object (not wrapped in a list).
"""

from __future__ import annotations

from typing import Any

from schemas import Conversation, Message


def looks_like_claude(data: Any) -> bool:
    conv = _first_conversation(data)
    return isinstance(conv, dict) and "chat_messages" in conv


def _first_conversation(data: Any) -> Any:
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _extract_text(msg: dict) -> str:
    """Prefer the flat ``text`` field; fall back to joining content blocks."""
    text = msg.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    parts: list[str] = []
    for block in msg.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            block_text = block.get("text")
            if isinstance(block_text, str):
                parts.append(block_text)
    return "\n".join(p for p in parts if p).strip()


def _normalize_conversation(conv: dict, index: int) -> Conversation:
    conversation_id = str(conv.get("uuid") or conv.get("id") or f"conversation-{index}")
    title = (conv.get("name") or conv.get("title") or "Untitled conversation").strip() or "Untitled conversation"

    messages: list[Message] = []
    for i, raw in enumerate(conv.get("chat_messages") or []):
        if not isinstance(raw, dict):
            continue
        content = _extract_text(raw)
        if not content:
            continue
        sender = raw.get("sender")
        role = "user" if sender == "human" else "assistant"
        message_id = str(raw.get("uuid") or f"m{i}")
        messages.append(
            Message(
                id=message_id,
                role=role,
                content=content,
                timestamp=raw.get("created_at"),
            )
        )

    return Conversation(conversation_id=conversation_id, title=title, messages=messages)


def normalize(data: Any) -> list[Conversation]:
    conversations_raw = data if isinstance(data, list) else [data]
    result: list[Conversation] = []
    for index, conv in enumerate(conversations_raw):
        if not isinstance(conv, dict) or "chat_messages" not in conv:
            continue
        normalized = _normalize_conversation(conv, index)
        if normalized.messages:
            result.append(normalized)
    return result
