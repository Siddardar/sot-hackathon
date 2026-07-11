"""The profiler: builds the prompt, calls the LLM, and validates the dossier.

Design notes
------------
* The leakage taxonomy (``taxonomy.py``) and the system prompt
  (``prompts/profiler_system.md``) are intentionally owned elsewhere. This module
  imports them if they exist and otherwise falls back to a minimal built-in
  taxonomy/prompt so the APIs are runnable today. When those files land, they are
  picked up automatically — no change here required.
* Every evidence quote returned by the model is validated against the message it
  cites. Ungrounded quotes are dropped; an inference left with no grounded
  evidence is discarded. This is the guard against the profiler hallucinating
  evidence, per the project plan.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import anthropic

from schemas import Evidence, Inference, Message, Redaction

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
MODEL = os.environ.get("PROFILER_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.environ.get("PROFILER_MAX_TOKENS", "16000"))
EFFORT = os.environ.get("PROFILER_EFFORT", "medium")  # low | medium | high | max
# Adaptive thinking improves inference quality; set PROFILER_THINKING=off to disable.
THINKING_ENABLED = os.environ.get("PROFILER_THINKING", "on").lower() not in ("off", "0", "false")
MAX_GENERATION_RETRIES = int(os.environ.get("PROFILER_MAX_RETRIES", "1"))

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "profiler_system.md"


class ProfilerError(RuntimeError):
    """Raised when the profiler cannot produce a valid dossier."""


# --------------------------------------------------------------------------- #
# Taxonomy interface (with graceful fallback)
# --------------------------------------------------------------------------- #
# The real taxonomy lives in taxonomy.py (owned separately). Until it exists we
# use this minimal set — matching the tiers in the project plan — so /analyze
# works end to end.
_FALLBACK_TAXONOMY: list[dict] = [
    {"id": "identity_direct", "name": "Direct identity", "tier": "A",
     "description": "Name, age, or employer the user stated outright."},
    {"id": "location_direct", "name": "Direct location", "tier": "A",
     "description": "City, address, or region the user stated outright."},
    {"id": "contact_direct", "name": "Direct contact", "tier": "A",
     "description": "Phone, email, or handles the user shared."},
    {"id": "location_inferred", "name": "Inferred location", "tier": "B",
     "description": "Location implied by references (transit, landmarks, weather)."},
    {"id": "occupation_inferred", "name": "Inferred occupation", "tier": "B",
     "description": "Job or field implied by jargon, schedule, or tasks."},
    {"id": "relationships", "name": "Relationships", "tier": "B",
     "description": "Partner, children, or family mentioned or implied."},
    {"id": "daily_routine", "name": "Daily routine", "tier": "B",
     "description": "Sleep, work hours, or commute patterns."},
    {"id": "socioeconomic", "name": "Socioeconomic status", "tier": "C",
     "description": "Income class implied by spending, vocabulary, or destinations."},
    {"id": "education_level", "name": "Education level", "tier": "C",
     "description": "Education implied by writing style and references."},
    {"id": "personality_traits", "name": "Personality traits", "tier": "C",
     "description": "Big-Five-style signals and communication style."},
    {"id": "health_physical", "name": "Physical health", "tier": "D",
     "description": "Symptoms, medication, or physical conditions."},
    {"id": "health_mental", "name": "Mental health", "tier": "D",
     "description": "Mood signals, therapy, or mental-health medication."},
    {"id": "sexuality_gender", "name": "Sexuality / gender", "tier": "D",
     "description": "Sexual orientation or gender identity."},
    {"id": "religion_beliefs", "name": "Religion / beliefs", "tier": "D",
     "description": "Religious or spiritual beliefs and practices."},
    {"id": "political_views", "name": "Political views", "tier": "D",
     "description": "Political leanings or affiliations."},
    {"id": "ethnicity_origin", "name": "Ethnicity / origin", "tier": "D",
     "description": "Ethnicity, nationality, or national origin."},
    {"id": "criminal_or_legal", "name": "Criminal / legal", "tier": "D",
     "description": "Legal trouble, offences, or interactions with law enforcement."},
]


def _load_taxonomy() -> list[dict]:
    """Return the taxonomy as a list of normalized dicts (id/name/tier/description)."""
    try:
        import taxonomy as taxonomy_module  # type: ignore
    except Exception:
        return _FALLBACK_TAXONOMY

    raw = getattr(taxonomy_module, "TAXONOMY", None)
    if not raw:
        return _FALLBACK_TAXONOMY

    normalized: list[dict] = []
    for entry in raw:
        if isinstance(entry, dict):
            get = entry.get
        else:  # dataclass / object with attributes
            get = lambda key, default=None, _e=entry: getattr(_e, key, default)  # noqa: E731
        normalized.append(
            {
                "id": str(get("id")),
                "name": str(get("name") or get("id")),
                "tier": str(get("tier") or "C"),
                "description": str(get("description") or ""),
                "example": get("example"),
            }
        )
    return normalized or _FALLBACK_TAXONOMY


def _build_taxonomy_section(taxonomy: list[dict]) -> str:
    """Render the taxonomy as a prompt block, grouped by tier."""
    tier_names = {
        "A": "Tier A — Explicit disclosures (user stated it outright)",
        "B": "Tier B — Direct inferences (one obvious step)",
        "C": "Tier C — Compound inferences (multi-signal profiling)",
        "D": "Tier D — Sensitive (GDPR Article 9)",
    }
    lines: list[str] = []
    for tier in ("A", "B", "C", "D"):
        entries = [c for c in taxonomy if c["tier"] == tier]
        if not entries:
            continue
        lines.append(tier_names.get(tier, f"Tier {tier}"))
        for cat in entries:
            line = f'  - {cat["id"]} ({cat["name"]}): {cat["description"]}'
            if cat.get("example"):
                line += f' e.g. {cat["example"]}'
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()


# --------------------------------------------------------------------------- #
# System prompt (with graceful fallback)
# --------------------------------------------------------------------------- #
_DEFAULT_SYSTEM_PROMPT = """\
You are a privacy auditor. Given a transcript of a conversation between a user and
an AI assistant, extract everything a data broker or adversary could infer about
the *user* from it.

Rules:
- Only infer things about the user. Never infer things about the assistant.
- Do not profile third parties (friends, family) the user merely mentions.
- For every inference, quote the exact sentence(s) from the USER's messages that
  support it. Copy the quote verbatim — do not paraphrase. Never invent evidence.
- If you are uncertain, use confidence "low" rather than omitting the inference.
- Assign each inference to one of the taxonomy categories below and use that
  category's tier.
- Return between 5 and 40 inferences.
"""


def _load_system_prompt(taxonomy_section: str) -> str:
    """Load the system prompt from prompts/, falling back to the built-in one.

    ``{taxonomy}`` in the prompt file is replaced with the rendered taxonomy; if
    the placeholder is absent, the taxonomy is appended.
    """
    if _SYSTEM_PROMPT_PATH.exists():
        template = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    else:
        template = _DEFAULT_SYSTEM_PROMPT

    if "{taxonomy}" in template:
        return template.replace("{taxonomy}", taxonomy_section)
    return f"{template}\n\nCategories:\n{taxonomy_section}"


# --------------------------------------------------------------------------- #
# Output schema for structured generation
# --------------------------------------------------------------------------- #
_DOSSIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "inferences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category_id": {"type": "string"},
                    "tier": {"type": "string", "enum": ["A", "B", "C", "D"]},
                    "claim": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "reasoning": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "message_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["message_id", "quote"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["category_id", "tier", "claim", "confidence", "reasoning", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["inferences"],
    "additionalProperties": False,
}


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #
def _render_transcript(messages: list[Message]) -> str:
    """Render the canonical transcript with each message tagged by id and role."""
    lines = [
        "Here is the transcript. Each message is tagged as [<message_id> | <role>].",
        "Quote exact substrings from USER messages only, and cite the message_id.",
        "",
    ]
    for msg in messages:
        lines.append(f"[{msg.id} | {msg.role}]: {msg.content}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Evidence grounding
# --------------------------------------------------------------------------- #
def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class ProfilerResult:
    inferences: list[Inference]
    model: str
    dropped_evidence: int = 0
    dropped_inferences: int = 0
    generations: int = 1


def _ground_inferences(
    raw_inferences: list[dict],
    messages: list[Message],
) -> tuple[list[Inference], int, int]:
    """Validate quotes against source messages; drop ungrounded evidence/inferences.

    Returns ``(inferences, dropped_evidence, dropped_inferences)``.
    """
    by_id = {m.id: _normalize_for_match(m.content) for m in messages}
    inferences: list[Inference] = []
    dropped_evidence = 0
    dropped_inferences = 0

    for raw in raw_inferences:
        evidence_list: list[Evidence] = []
        for ev in raw.get("evidence") or []:
            message_id = str(ev.get("message_id", ""))
            quote = str(ev.get("quote", ""))
            haystack = by_id.get(message_id)
            if haystack is not None and _normalize_for_match(quote) and _normalize_for_match(quote) in haystack:
                evidence_list.append(Evidence(message_id=message_id, quote=quote))
            else:
                dropped_evidence += 1

        if not evidence_list:
            dropped_inferences += 1
            continue

        try:
            inferences.append(
                Inference(
                    category_id=str(raw.get("category_id", "")),
                    tier=raw.get("tier"),
                    claim=str(raw.get("claim", "")),
                    confidence=raw.get("confidence"),
                    reasoning=str(raw.get("reasoning", "")),
                    evidence=evidence_list,
                )
            )
        except Exception:
            # Malformed enum/field from the model — skip this one rather than fail.
            dropped_inferences += 1

    return inferences, dropped_evidence, dropped_inferences


# --------------------------------------------------------------------------- #
# LLM call
# --------------------------------------------------------------------------- #
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProfilerError(
                "ANTHROPIC_API_KEY is not set. Export it before calling the profiler."
            )
        _client = anthropic.Anthropic()
    return _client


def _call_model(system_prompt: str, transcript: str) -> list[dict]:
    """Run one structured, streamed generation and return the raw inference dicts."""
    client = _get_client()

    output_config: dict[str, Any] = {
        "effort": EFFORT,
        "format": {"type": "json_schema", "schema": _DOSSIER_SCHEMA},
    }
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "output_config": output_config,
        "messages": [{"role": "user", "content": transcript}],
    }
    if THINKING_ENABLED:
        kwargs["thinking"] = {"type": "adaptive"}

    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()

    text = next((block.text for block in message.content if block.type == "text"), None)
    if not text:
        raise ProfilerError("The model returned no text output.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfilerError(f"The model output was not valid JSON: {exc}") from exc

    inferences = payload.get("inferences")
    if not isinstance(inferences, list):
        raise ProfilerError("The model output did not contain an 'inferences' array.")
    return inferences


def run_profiler(messages: list[Message]) -> ProfilerResult:
    """Profile a transcript and return validated inferences.

    Retries the whole generation (up to ``PROFILER_MAX_RETRIES``) only if a run
    produces inferences but *all* of them fail evidence grounding — i.e. the
    model hallucinated every quote.
    """
    if not messages:
        return ProfilerResult(inferences=[], model=MODEL, generations=0)

    taxonomy = _load_taxonomy()
    system_prompt = _load_system_prompt(_build_taxonomy_section(taxonomy))
    transcript = _render_transcript(messages)

    total_dropped_evidence = 0
    total_dropped_inferences = 0
    attempts = 0

    for attempt in range(MAX_GENERATION_RETRIES + 1):
        attempts = attempt + 1
        raw = _call_model(system_prompt, transcript)
        inferences, dropped_ev, dropped_inf = _ground_inferences(raw, messages)
        total_dropped_evidence += dropped_ev
        total_dropped_inferences += dropped_inf

        # Success, or nothing to retry (the model genuinely found nothing).
        if inferences or not raw:
            return ProfilerResult(
                inferences=inferences,
                model=MODEL,
                dropped_evidence=total_dropped_evidence,
                dropped_inferences=total_dropped_inferences,
                generations=attempts,
            )
        # else: the model returned inferences but all were ungrounded — retry.

    return ProfilerResult(
        inferences=[],
        model=MODEL,
        dropped_evidence=total_dropped_evidence,
        dropped_inferences=total_dropped_inferences,
        generations=attempts,
    )


# --------------------------------------------------------------------------- #
# Redaction + diffing
# --------------------------------------------------------------------------- #
_REDACTION_TOKEN = "[REDACTED]"


def mask_messages(
    messages: list[Message],
    redacted_message_ids: list[str],
    redactions: Optional[list[Redaction]] = None,
) -> list[Message]:
    """Return a copy of ``messages`` with the requested spans masked.

    Whole-message redactions replace the entire content; character-range
    redactions replace only the given span. A message may have both applied.
    """
    redacted_ids = set(redacted_message_ids or [])
    ranges: dict[str, list[Redaction]] = {}
    for r in redactions or []:
        ranges.setdefault(r.message_id, []).append(r)

    masked: list[Message] = []
    for msg in messages:
        content = msg.content
        if msg.id in redacted_ids:
            content = _REDACTION_TOKEN
        elif msg.id in ranges:
            content = _apply_ranges(content, ranges[msg.id])
        masked.append(msg.model_copy(update={"content": content}))
    return masked


def _apply_ranges(content: str, ranges: list[Redaction]) -> str:
    # Apply from right to left so earlier indices stay valid.
    for r in sorted(ranges, key=lambda x: x.start, reverse=True):
        start = max(0, min(r.start, len(content)))
        end = max(start, min(r.end, len(content)))
        content = content[:start] + _REDACTION_TOKEN + content[end:]
    return content


def _signature(inf: Inference) -> tuple[str, str]:
    return (inf.category_id, _normalize_for_match(inf.claim))


def diff_dossiers(original: list[Inference], updated: list[Inference]):
    """Compute what redaction eliminated/added, matching on (category, claim).

    Returns a ``RedactDiff``.
    """
    from schemas import RedactDiff  # local import to avoid a cycle at module load

    updated_sigs = {_signature(i) for i in updated}
    original_sigs = {_signature(i) for i in original}

    eliminated = [i for i in original if _signature(i) not in updated_sigs]
    added = [i for i in updated if _signature(i) not in original_sigs]
    retained_count = len(original) - len(eliminated)
    eliminated_sensitive = sum(1 for i in eliminated if i.tier == "D")

    n_msgs = "inference" if len(eliminated) == 1 else "inferences"
    summary = (
        f"Redaction eliminated {len(eliminated)} {n_msgs}"
        f" (including {eliminated_sensitive} sensitive-tier)"
        f" and surfaced {len(added)} new."
    )

    return RedactDiff(
        eliminated=eliminated,
        added=added,
        retained_count=retained_count,
        eliminated_sensitive_count=eliminated_sensitive,
        summary=summary,
    )
