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

from typing import Any, Optional

from schemas import Account, Conversation, Message, ProjectMemory, ProviderMemory


def parse_users(data: Any) -> Optional[Account]:
    """Extract the account identity from an account-info payload.

    Handles both providers' shapes:
      * Claude ``users.json`` — a list with a single object
        ``[{"full_name", "email_address", "verified_phone_number", ...}]``
      * ChatGPT ``user.json`` — a single object
        ``{"email", "birth_year", "id", "chatgpt_plus_user"}``
    """
    user = data[0] if isinstance(data, list) and data else data
    if not isinstance(user, dict):
        return None
    name = user.get("full_name") or user.get("name")
    email = user.get("email_address") or user.get("email")
    phone = user.get("verified_phone_number") or user.get("phone_number")
    if not any((name, email, phone)):
        return None
    return Account(name=name, email=email, phone=phone)


def parse_memories(data: Any) -> Optional[ProviderMemory]:
    """Extract the provider's own inferred profile from ``memories.json``.

    ``memories.json`` is a list with a single object:
        [{"account_uuid", "conversations_memory": "<markdown>",
          "project_memories": {"<project_uuid>": "<markdown>", ...}}]
    """
    item = data[0] if isinstance(data, list) and data else data
    if not isinstance(item, dict):
        return None

    conv_mem = item.get("conversations_memory")
    conv_mem = conv_mem.strip() if isinstance(conv_mem, str) and conv_mem.strip() else None

    project_memories: list[ProjectMemory] = []
    for project_id, text in (item.get("project_memories") or {}).items():
        if isinstance(text, str) and text.strip():
            project_memories.append(ProjectMemory(project_id=str(project_id), memory=text.strip()))

    if not conv_mem and not project_memories:
        return None
    return ProviderMemory(conversations_memory=conv_mem, project_memories=project_memories)


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
