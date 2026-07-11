"""Normalizer for ChatGPT data exports (``conversations.json``).

ChatGPT exports are a JSON array of conversation objects. Each conversation
stores its messages as a ``mapping`` tree (to accommodate edits/regenerations)
rather than a flat list:

    {
      "title": "...",
      "create_time": 1690000000.0,
      "current_node": "<leaf id>",
      "mapping": {
        "<node id>": {
          "id": "<node id>",
          "message": {
            "id": "...",
            "author": {"role": "user"|"assistant"|"system"|"tool"},
            "content": {"content_type": "text", "parts": ["..."]},
            "create_time": 1690000000.0
          },
          "parent": "<parent id>|null",
          "children": ["<child id>", ...]
        }
      }
    }

The canonical linear transcript is the path from the root to ``current_node``.
When ``current_node`` is absent we walk children from the root, taking the
first child at each step.
"""

from __future__ import annotations

from typing import Any, Optional

from schemas import Conversation, Message


def looks_like_chatgpt(data: Any) -> bool:
    conv = _first_conversation(data)
    return isinstance(conv, dict) and isinstance(conv.get("mapping"), dict)


def _first_conversation(data: Any) -> Any:
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _extract_text(message: dict) -> str:
    content = message.get("content")
    if not isinstance(content, dict):
        return ""
    if content.get("content_type") not in (None, "text", "multimodal_text"):
        return ""
    parts = content.get("parts") or []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict):
            # Multimodal parts occasionally carry text under a nested key.
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(c for c in chunks if c).strip()


def _ordered_node_ids(mapping: dict, current_node: Optional[str]) -> list[str]:
    """Return node ids from root to leaf for the active branch."""
    # Preferred: walk parent pointers up from current_node, then reverse.
    if current_node and current_node in mapping:
        chain: list[str] = []
        node_id: Optional[str] = current_node
        seen: set[str] = set()
        while node_id and node_id in mapping and node_id not in seen:
            seen.add(node_id)
            chain.append(node_id)
            node_id = mapping[node_id].get("parent")
        chain.reverse()
        return chain

    # Fallback: find the root (node with no parent) and follow first children.
    root_id = next(
        (nid for nid, node in mapping.items() if not node.get("parent")),
        None,
    )
    if root_id is None:
        return list(mapping.keys())

    chain = []
    node_id = root_id
    seen = set()
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        chain.append(node_id)
        children = mapping[node_id].get("children") or []
        node_id = children[0] if children else None
    return chain


def _normalize_conversation(conv: dict, index: int) -> Conversation:
    mapping = conv.get("mapping") or {}
    conversation_id = str(conv.get("conversation_id") or conv.get("id") or f"conversation-{index}")
    title = (conv.get("title") or "Untitled conversation").strip() or "Untitled conversation"

    messages: list[Message] = []
    for node_id in _ordered_node_ids(mapping, conv.get("current_node")):
        node = mapping.get(node_id) or {}
        message = node.get("message")
        if not isinstance(message, dict):
            continue

        role = (message.get("author") or {}).get("role")
        if role not in ("user", "assistant"):
            continue  # skip system/tool nodes

        content = _extract_text(message)
        if not content:
            continue

        create_time = message.get("create_time")
        messages.append(
            Message(
                id=str(message.get("id") or node_id),
                role=role,
                content=content,
                timestamp=str(create_time) if create_time is not None else None,
            )
        )

    return Conversation(conversation_id=conversation_id, title=title, messages=messages)


def normalize(data: Any) -> list[Conversation]:
    conversations_raw = data if isinstance(data, list) else [data]
    result: list[Conversation] = []
    for index, conv in enumerate(conversations_raw):
        if not isinstance(conv, dict) or not isinstance(conv.get("mapping"), dict):
            continue
        normalized = _normalize_conversation(conv, index)
        if normalized.messages:
            result.append(normalized)
    return result
