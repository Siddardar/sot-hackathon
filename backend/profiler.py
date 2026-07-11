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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from schemas import Evidence, Inference, Message, Redaction

# Load backend/.env so GOOGLE_API_KEY (and other config) is picked up without
# having to export it or pass --env-file. Existing env vars take precedence.
load_dotenv(Path(__file__).parent / ".env")


def _google_api_key() -> Optional[str]:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def api_key_configured() -> bool:
    return bool(_google_api_key())


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
MODEL = os.environ.get("PROFILER_MODEL", "gemini-3.5-flash")
MAX_TOKENS = int(os.environ.get("PROFILER_MAX_TOKENS", "16000"))
TEMPERATURE = float(os.environ.get("PROFILER_TEMPERATURE", "0.3"))
MAX_GENERATION_RETRIES = int(os.environ.get("PROFILER_MAX_RETRIES", "1"))


def use_mock() -> bool:
    """Whether to return a sample dossier instead of calling the LLM.

    ``PROFILER_MOCK`` = ``1``/``on`` forces mock, ``0``/``off`` forces real; the
    default ``auto`` mocks whenever no Gemini API key is configured — so the
    whole pipeline works end to end before the prompts/keys are wired up.
    """
    setting = os.environ.get("PROFILER_MOCK", "auto").lower()
    if setting in ("1", "true", "on", "yes"):
        return True
    if setting in ("0", "false", "off", "no"):
        return False
    return not api_key_configured()

# Prompts live at the repo root (../prompts relative to this file). Override the
# location with GLASSHOUSE_PROMPTS_DIR if needed.
_PROMPTS_DIR = Path(
    os.environ.get("GLASSHOUSE_PROMPTS_DIR") or (Path(__file__).resolve().parent.parent / "prompts")
)
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system_prompt.md"
_TIER_PROMPT_FILES = {
    "A": "tier_a_prompt.md",
    "B": "tier_b_prompt.md",
    "C": "tier_c_prompt.md",
    "D": "tier_d_prompt.md",
}
TIERS: tuple[str, ...] = ("A", "B", "C", "D")

# Category ids, copied from prompts/system_prompt.md. A/B/C use the non-sensitive
# set; Tier D uses only the sensitive set (sensitivity overrides A/B/C).
_NON_SENSITIVE_CATEGORIES = [
    "identity", "location", "contact", "occupation", "relationships",
    "daily_routine", "socioeconomic", "education_level", "personality_traits",
    "interests_lifestyle", "technical_profile",
]
_SENSITIVE_CATEGORIES = [
    "health_physical", "health_mental", "sexuality_gender", "religion_beliefs",
    "political_views", "ethnicity_origin", "criminal_or_legal",
]
_TIER_CATEGORIES = {
    "A": _NON_SENSITIVE_CATEGORIES,
    "B": _NON_SENSITIVE_CATEGORIES,
    "C": _NON_SENSITIVE_CATEGORIES,
    "D": _SENSITIVE_CATEGORIES,
}


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


def _load_system_prompt() -> str:
    """Load the shared system prompt (``prompts/system_prompt.md``) verbatim.

    The category list is baked into the prompt, so no taxonomy injection is
    needed. Falls back to the built-in default if the file is missing.
    """
    if _SYSTEM_PROMPT_PATH.exists():
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return _DEFAULT_SYSTEM_PROMPT


def _load_tier_prompt(tier: str) -> str:
    """Load the per-tier prompt (``prompts/tier_{a,b,c,d}_prompt.md``)."""
    path = _PROMPTS_DIR / _TIER_PROMPT_FILES[tier]
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f'This is the Tier {tier} pass. Set tier to "{tier}" for every finding.'


# --------------------------------------------------------------------------- #
# Output schema for structured generation (one per tier)
# --------------------------------------------------------------------------- #
def _tier_response_schema(tier: str) -> dict[str, Any]:
    """Build the ``findings`` JSON schema for a single tier pass.

    ``tier`` is fixed and ``category_id`` is restricted to that tier's allowed
    categories (Tier D → the sensitive set), matching the prompts exactly.
    """
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "enum": ["self", "third_party"]},
                        "category_id": {"type": "string", "enum": _TIER_CATEGORIES[tier]},
                        "tier": {"type": "string", "enum": [tier]},
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
                    "required": ["subject", "category_id", "tier", "claim", "confidence", "reasoning", "evidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["findings"],
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
    mock: bool = False
    tier_counts: dict[str, int] = field(default_factory=dict)
    tier_errors: dict[str, str] = field(default_factory=dict)


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

        subject = raw.get("subject")
        try:
            inferences.append(
                Inference(
                    subject=subject if subject in ("self", "third_party") else "self",
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
# Mock dossier (used until prompts/keys are wired up)
# --------------------------------------------------------------------------- #
# (keywords, category_id, tier, claim, confidence, reasoning)
_MOCK_RULES: list[tuple[tuple[str, ...], str, str, str, str, str]] = [
    (("morocco", "malta", "itinerary", "trip", "travel", "flying"),
     "socioeconomic", "C", "Travels internationally and plans multi-day trips", "medium",
     "Discussing international travel plans signals disposable income and leisure travel habits."),
    (("fpga", "vivado", "cva6", "risc-v", "processor", "mmu", "vhdl", "verilog"),
     "occupation", "B", "Works in hardware / computer architecture", "high",
     "Hardware-design jargon points to an engineering or CS background."),
    (("wireshark", "scapy", "packet", "airdrop", "ssh", "tunnel", "network"),
     "occupation", "B", "Comfortable with networking and systems analysis", "medium",
     "References to packet capture and networking tools indicate technical, systems-level work."),
    (("python", "venv", "homebrew", "macos", "macbook", "jupyter"),
     "occupation", "B", "Develops software, likely on a Mac", "medium",
     "Developer tooling and a macOS environment suggest a software-development workflow."),
    (("student", "assignment", "course", "hackathon", "ects", "university", "lecture"),
     "education_level", "C", "Is a student in higher education", "medium",
     "Coursework and academic-credit references indicate current enrolment."),
    (("azure", "aws", "cloud", "vm", "server", "minecraft"),
     "occupation", "B", "Runs cloud infrastructure for personal/side projects", "low",
     "Managing cloud VMs suggests hands-on infrastructure experience."),
    (("anxiety", "therapy", "ssri", "depress", "insomnia", "burnout"),
     "health_mental", "D", "May be managing a mental-health condition", "low",
     "Mentions of mood, therapy, or medication are sensitive health signals."),
]

_SENTENCE_BOUNDARY = re.compile(r"[.!?\n]")


def _sentence_around(content: str, match_start: int, match_end: int) -> str:
    """Return the sentence (verbatim substring) containing a keyword match."""
    left = 0
    for m in _SENTENCE_BOUNDARY.finditer(content, 0, match_start):
        left = m.end()
    right_match = _SENTENCE_BOUNDARY.search(content, match_end)
    right = right_match.start() if right_match else len(content)
    quote = content[left:right].strip()
    return quote[:240] if len(quote) > 240 else quote


def _mock_raw_inferences(messages: list[Message]) -> list[dict]:
    """Build a realistic, evidence-grounded sample dossier without an LLM."""
    user_messages = [m for m in messages if m.role == "user"]
    raw: list[dict] = []
    used_categories: set[str] = set()

    for keywords, category_id, tier, claim, confidence, reasoning in _MOCK_RULES:
        if category_id in used_categories:
            continue
        # Whole-word match so e.g. "ects" doesn't match inside "Projects".
        pattern = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b")
        for msg in user_messages:
            match = pattern.search(msg.content.lower())
            if not match:
                continue
            quote = _sentence_around(msg.content, match.start(), match.end())
            if not quote:
                continue
            raw.append({
                "subject": "self",
                "category_id": category_id, "tier": tier, "claim": claim,
                "confidence": confidence, "reasoning": reasoning,
                "evidence": [{"message_id": msg.id, "quote": quote}],
            })
            used_categories.add(category_id)
            break

    # Ensure the dossier is never empty: quote the first user message.
    if not raw and user_messages:
        first = user_messages[0]
        quote = _sentence_around(first.content, 0, 0) or first.content[:180]
        raw.append({
            "subject": "self",
            "category_id": "personality_traits", "tier": "C",
            "claim": "Engages AI assistants for detailed, technical help",
            "confidence": "low",
            "reasoning": "Sample inference — the profiler prompt is not wired up yet.",
            "evidence": [{"message_id": first.id, "quote": quote}],
        })
    return raw


# --------------------------------------------------------------------------- #
# LLM call
# --------------------------------------------------------------------------- #
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = _google_api_key()
        if not api_key:
            raise ProfilerError(
                "GOOGLE_API_KEY or GEMINI_API_KEY is not set. Export one before calling the profiler."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _call_tier(tier: str, system_prompt: str, transcript: str) -> list[dict]:
    """Run one tier pass and return its raw ``findings`` dicts (tier stamped)."""
    client = _get_client()
    system_instruction = f"{system_prompt}\n\n{_load_tier_prompt(tier)}"

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=transcript,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                response_mime_type="application/json",
                response_json_schema=_tier_response_schema(tier),
            ),
        )
    except genai_errors.APIError as exc:
        raise ProfilerError(f"Gemini API error (tier {tier}): {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — keep API-specific failures user-visible
        raise ProfilerError(f"Gemini generation failed (tier {tier}): {exc}") from exc

    payload = response.parsed
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()
    if payload is None:
        text = response.text
        if not text:
            raise ProfilerError(f"The model returned no text output (tier {tier}).")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProfilerError(f"The model output was not valid JSON (tier {tier}): {exc}") from exc

    if not isinstance(payload, dict):
        raise ProfilerError(f"The model output was not a JSON object (tier {tier}).")

    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ProfilerError(f"The model output did not contain a 'findings' array (tier {tier}).")

    for finding in findings:
        if isinstance(finding, dict):
            finding["tier"] = tier  # trust the pass, not the model, for the tier
    return findings


def test_gemini_api(prompt: str = "Reply with exactly: Gemini API test ok") -> dict[str, Any]:
    """Make a minimal real Gemini call to verify API key, model, and SDK wiring."""
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except genai_errors.APIError as exc:
        raise ProfilerError(f"Gemini API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — keep SDK/config failures visible
        raise ProfilerError(f"Gemini test call failed: {exc}") from exc

    text = response.text or "".join(
        part.text or ""
        for candidate in response.candidates or []
        for part in (candidate.content.parts if candidate.content and candidate.content.parts else [])
    )
    if not text:
        raise ProfilerError("Gemini test call returned no text output.")

    return {
        "ok": True,
        "model": MODEL,
        "text": text.strip(),
    }


def run_profiler(messages: list[Message]) -> ProfilerResult:
    """Profile a transcript and return validated inferences.

    Retries the whole generation (up to ``PROFILER_MAX_RETRIES``) only if a run
    produces inferences but *all* of them fail evidence grounding — i.e. the
    model hallucinated every quote.
    """
    if not messages:
        return ProfilerResult(inferences=[], model=MODEL, generations=0)

    # Mock mode: return a grounded sample dossier without calling the LLM. Runs
    # through the same grounding path so evidence quotes are guaranteed valid.
    if use_mock():
        inferences, dropped_ev, dropped_inf = _ground_inferences(
            _mock_raw_inferences(messages), messages
        )
        return ProfilerResult(
            inferences=inferences,
            model="mock",
            dropped_evidence=dropped_ev,
            dropped_inferences=dropped_inf,
            generations=0,
            mock=True,
        )

    _get_client()  # init once up front (fails fast if no key; avoids a thread race)
    system_prompt = _load_system_prompt()
    transcript = _render_transcript(messages)

    all_inferences: list[Inference] = []
    tier_counts: dict[str, int] = {}
    tier_errors: dict[str, str] = {}
    total_dropped_evidence = 0
    total_dropped_inferences = 0

    def _run_tier(tier: str) -> tuple[list[Inference], int, int]:
        return _ground_inferences(_call_tier(tier, system_prompt, transcript), messages)

    # One focused pass per tier, run concurrently — latency ≈ the slowest tier.
    with ThreadPoolExecutor(max_workers=len(TIERS)) as executor:
        futures = {executor.submit(_run_tier, tier): tier for tier in TIERS}
        for future in as_completed(futures):
            tier = futures[future]
            try:
                inferences, dropped_ev, dropped_inf = future.result()
            except ProfilerError as exc:
                tier_errors[tier] = str(exc)
                continue
            all_inferences.extend(inferences)
            tier_counts[tier] = len(inferences)
            total_dropped_evidence += dropped_ev
            total_dropped_inferences += dropped_inf

    # If every tier failed, surface the error instead of returning empty silently.
    if len(tier_errors) == len(TIERS):
        raise ProfilerError("; ".join(f"{t}: {m}" for t, m in sorted(tier_errors.items())))

    # Order findings A -> B -> C -> D for a stable, tier-grouped stream.
    tier_order = {t: i for i, t in enumerate(TIERS)}
    all_inferences.sort(key=lambda inf: tier_order.get(inf.tier, 99))

    return ProfilerResult(
        inferences=all_inferences,
        model=MODEL,
        dropped_evidence=total_dropped_evidence,
        dropped_inferences=total_dropped_inferences,
        generations=1,
        tier_counts=tier_counts,
        tier_errors=tier_errors,
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
