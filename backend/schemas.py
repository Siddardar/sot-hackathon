"""Pydantic models for the API surface and the profiler-LLM output.

These are the single source of truth for the canonical transcript format and the
dossier schema. Both the normalizers and the profiler produce objects that
validate against these models, and FastAPI uses them for request/response
serialization.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["user", "assistant"]
Tier = Literal["A", "B", "C", "D"]
Confidence = Literal["low", "medium", "high"]
Subject = Literal["self", "third_party"]


# --------------------------------------------------------------------------- #
# Canonical transcript
# --------------------------------------------------------------------------- #
class Message(BaseModel):
    """One message in a canonical transcript.

    Every message carries a stable ``id`` so the frontend can highlight the
    exact source of an inference and the profiler can cite it.
    """

    id: str
    role: Role
    content: str
    timestamp: Optional[str] = None


class Conversation(BaseModel):
    """A single normalized conversation."""

    conversation_id: str
    title: str
    messages: list[Message]


class ConversationSummary(BaseModel):
    """Lightweight view of a conversation for the picker screen."""

    conversation_id: str
    title: str
    message_count: int
    preview: str


class Account(BaseModel):
    """Known account identity, taken from the export's ``users.json``.

    This is ground-truth metadata the user gave the provider (not inferred from
    the transcript), so it has no sentence to quote — the frontend surfaces it
    separately as guaranteed, Tier-A identity leakage.
    """

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ProjectMemory(BaseModel):
    """One per-project memory the provider retained."""

    project_id: str
    memory: str


class ProviderMemory(BaseModel):
    """The provider's *own* inferred profile of the user, from ``memories.json``.

    This is not produced by our tool — it is what the AI provider already
    remembers and has inferred across conversations. The frontend surfaces it as
    a "what the provider already knows about you" panel, distinct from our
    transcript-derived, evidence-linked dossier.
    """

    conversations_memory: Optional[str] = None
    project_memories: list[ProjectMemory] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# /parse
# --------------------------------------------------------------------------- #
class ParseResponse(BaseModel):
    """Result of parsing an uploaded export.

    Returns the full canonical conversations (so the frontend can pass the
    chosen one straight to ``/analyze`` without re-uploading) plus a lightweight
    summary list for the picker. When the upload is a full account export, the
    known ``account`` identity is included.
    """

    format: str = Field(description="The format that was detected/used, e.g. 'claude', 'chatgpt', 'generic'.")
    conversations: list[Conversation]
    summaries: list[ConversationSummary]
    account: Optional[Account] = None
    memory: Optional[ProviderMemory] = None


# --------------------------------------------------------------------------- #
# Dossier (LLM output)
# --------------------------------------------------------------------------- #
class Evidence(BaseModel):
    """A quoted span that supports an inference."""

    message_id: str
    quote: str = Field(description="Exact substring copied from the referenced message.")


class Inference(BaseModel):
    """One thing a profiler could infer about the user, with its evidence.

    (In the prompts these are called "findings" and carry a ``subject``.)
    """

    subject: Subject = "self"
    category_id: str = Field(description="Matches a category id in the taxonomy.")
    tier: Tier
    claim: str = Field(description="Short natural-language inference about the user.")
    confidence: Confidence
    reasoning: str = Field(description="1-2 sentences on how the claim was inferred.")
    evidence: list[Evidence]


# --------------------------------------------------------------------------- #
# /analyze
# --------------------------------------------------------------------------- #
class AnalyzeRequest(BaseModel):
    conversation_id: Optional[str] = None
    messages: list[Message]


# --------------------------------------------------------------------------- #
# /redact_rerun
# --------------------------------------------------------------------------- #
class Redaction(BaseModel):
    """A character-range redaction inside a single message (finer than whole-message)."""

    message_id: str
    start: int
    end: int


class RedactRerunRequest(BaseModel):
    messages: list[Message]
    redacted_message_ids: list[str] = Field(
        default_factory=list,
        description="Message ids to fully mask before re-running the profiler.",
    )
    redactions: list[Redaction] = Field(
        default_factory=list,
        description="Optional finer-grained character-range redactions.",
    )
    original_inferences: list[Inference] = Field(
        default_factory=list,
        description="The dossier from the original /analyze run, used to compute the diff.",
    )
    conversation_id: Optional[str] = None


class RedactDiff(BaseModel):
    """What changed between the original dossier and the re-run on the masked transcript."""

    eliminated: list[Inference] = Field(description="Inferences present before but gone after redaction.")
    added: list[Inference] = Field(description="Inferences that only appeared after redaction.")
    retained_count: int = Field(description="Inferences present in both runs.")
    eliminated_sensitive_count: int = Field(description="Eliminated inferences that were Tier D (sensitive).")
    summary: str


class RedactRerunResponse(BaseModel):
    inferences: list[Inference] = Field(description="The new dossier for the masked transcript.")
    diff: RedactDiff
