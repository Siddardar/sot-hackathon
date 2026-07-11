"""
taxonomy_v3.py - Personal Data Leak: leakage taxonomy.

The single source of truth for what the profiler looks for. This matches
profiler_prompts_v3.md exactly: every category the prompt can emit is defined
here, every tier the prompt names (S, M, A, B, C, D) exists here, and every
category declares the source_scope the prompt's SOURCE SCOPE RULE enforces.

Design notes (justify these in the report, not the prompt):
  - Tier S (stated profile) is weighted 0. It is not leakage; the person typed
    it into a settings box on purpose. It is reported so the picture is complete.
  - Tier M (metadata) is a distinct leakage surface, visible only in an export,
    that content-only tools miss.
  - Every finding also carries a `subject` (self | third_party) set by the model,
    not the taxonomy. Third-party findings are discarded by the backend.
  - The backend OVERWRITES the model's tier from this file (validation step 2),
    so the tier here is authoritative.
"""

from dataclasses import dataclass
from typing import Literal

Tier = Literal["S", "M", "A", "B", "C", "D"]
SourceScope = Literal["user_messages", "metadata", "stated_profile"]


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    tier: Tier
    source_scope: SourceScope
    description: str
    example: str


TIER_NAMES: dict[str, str] = {
    "S": "Stated profile (custom instructions or saved memory, not conversation)",
    "M": "Metadata inference (drawn from timestamps, cadence, or language, not content)",
    "A": "Explicit disclosure (the user stated it outright in conversation)",
    "B": "Direct inference (one obvious reasoning step from what was said)",
    "C": "Compound inference (several weak signals combined into a profile trait)",
    "D": "Sensitive inference (special category data under GDPR Article 9)",
}

# S contributes 0: it was volunteered into a settings box, not leaked.
# The weights are a design choice. The rationale is in taxonomy_methodology.md.
TIER_WEIGHTS: dict[str, int] = {"S": 0, "M": 2, "A": 1, "B": 2, "C": 3, "D": 5}

TIER_ORDER = ["S", "M", "A", "B", "C", "D"]


CATEGORIES: list[Category] = [
    # ---------------- Tier S: stated profile ----------------
    Category(
        id="stated_profile",
        name="Stated profile",
        tier="S",
        source_scope="stated_profile",
        description=(
            "Anything the user deliberately typed into custom instructions or saved memory. "
            "Report it, but never count it as leakage and never merge it with conversational findings."
        ),
        example="Custom instructions: 'I am a PhD student in Delft, respond concisely.'",
    ),

    # ---------------- Tier M: metadata ----------------
    Category(
        id="timezone_inferred",
        name="Inferred time zone",
        tier="M",
        source_scope="metadata",
        description="Time zone or geographic band inferred from the clock times of the user's messages.",
        example="Messages cluster 08:00-23:00 UTC+1 and never at 03:00 -> lives in or near Central Europe.",
    ),
    Category(
        id="activity_pattern",
        name="Activity pattern",
        tier="M",
        source_scope="metadata",
        description="Sleep, work rhythm, or disrupted routine inferred from when messages are sent.",
        example="Regular messages between 01:00 and 04:00 across many nights -> night shift or insomnia.",
    ),
    Category(
        id="usage_intensity",
        name="Usage intensity and dependence",
        tier="M",
        source_scope="metadata",
        description="How heavily the user relies on the assistant, inferred from message volume and session length.",
        example="Forty messages in one unbroken hour on a personal problem -> high reliance for emotional support.",
    ),
    Category(
        id="language_origin",
        name="Language background",
        tier="M",
        source_scope="user_messages",
        description="Native language or region inferred from grammar patterns, calques, or spelling conventions.",
        example="Consistent article omission and 'informations' -> likely Slavic or Romance first language.",
    ),

    # ---------------- Tier A: explicit ----------------
    Category(
        id="identity_direct",
        name="Stated identity",
        tier="A",
        source_scope="user_messages",
        description="Name, age, employer, or institution the user states about themselves in conversation.",
        example="'My name is Priya and I work at Bosch.'",
    ),
    Category(
        id="location_direct",
        name="Stated location",
        tier="A",
        source_scope="user_messages",
        description="A city, neighbourhood, or address the user states outright.",
        example="'I live in Delft.'",
    ),
    Category(
        id="contact_direct",
        name="Stated contact details",
        tier="A",
        source_scope="user_messages",
        description="Phone numbers, email addresses, usernames, or social handles belonging to the user.",
        example="'Email me at r.chen@gmail.com.'",
    ),
    Category(
        id="pasted_material",
        name="Pasted documents and code",
        tier="A",
        source_scope="user_messages",
        description=(
            "Content the user pasted rather than wrote: CVs, emails, contracts, code, medical letters. "
            "Exports preserve these in full. Report once, name the document type and what it exposes, "
            "and do not enumerate every line."
        ),
        example="Pasted a CV containing a full employment history and a home address.",
    ),

    # ---------------- Tier B: direct inference ----------------
    Category(
        id="location_inferred",
        name="Inferred location",
        tier="B",
        source_scope="user_messages",
        description="Location deduced from transport, weather, currency, institutions, or slang.",
        example="'The tram to campus was late again.' -> lives in a tram city, near a university.",
    ),
    Category(
        id="occupation_inferred",
        name="Inferred occupation",
        tier="B",
        source_scope="user_messages",
        description="Job, field, or seniority deduced from jargon, tools, or work rhythm.",
        example="'Standup ran long and I still have to review two PRs.' -> software engineer.",
    ),
    Category(
        id="employer_inferred",
        name="Inferred employer or workplace",
        tier="B",
        source_scope="user_messages",
        description="A specific organisation inferred from internal tool names, project names, or pasted work material.",
        example="Pasted a Jira ticket with an internal product codename.",
    ),
    Category(
        id="relationships",
        name="Relationships and household",
        tier="B",
        source_scope="user_messages",
        description="Partner, children, parents, roommates, pets, or caregiving duties of the user.",
        example="'I need a dinner idea my toddler will actually eat.' -> has a young child.",
    ),

    # ---------------- Tier C: compound inference ----------------
    Category(
        id="socioeconomic",
        name="Socioeconomic status",
        tier="C",
        source_scope="user_messages",
        description="Income bracket, housing situation, or financial pressure inferred from spending, travel, or worry.",
        example="'Can I get by on 900 a month for rent and food?' -> low disposable income.",
    ),
    Category(
        id="education_level",
        name="Education level",
        tier="C",
        source_scope="user_messages",
        description="Education inferred from vocabulary, references, writing style, or the questions asked.",
        example="Asks for help citing in APA and mentions a thesis -> university student.",
    ),
    Category(
        id="personality_traits",
        name="Personality and communication style",
        tier="C",
        source_scope="user_messages",
        description="Stable dispositional traits inferred across the conversation, such as conscientiousness or anxiety.",
        example="Repeated apologies and hedging -> high agreeableness, low assertiveness.",
    ),
    Category(
        id="life_events",
        name="Life events and transitions",
        tier="C",
        source_scope="user_messages",
        description=(
            "Major transitions inferred by tracking the same topic across a long export: "
            "a job change, a breakup, a move, a bereavement, a new diagnosis."
        ),
        example="Cover letters in March, then relocation questions in May -> changed jobs and moved.",
    ),

    # ---------------- Tier D: sensitive (GDPR Art. 9) ----------------
    Category(
        id="health_physical",
        name="Physical health",
        tier="D",
        source_scope="user_messages",
        description="Symptoms, diagnoses, medication, disability, or pregnancy.",
        example="'What foods should I avoid with metformin?' -> likely type 2 diabetes.",
    ),
    Category(
        id="health_mental",
        name="Mental health",
        tier="D",
        source_scope="user_messages",
        description=(
            "Mood, therapy, psychiatric medication, or distress signals. Report as a signal a profiler "
            "could read, never as a clinical diagnosis."
        ),
        example="'I can't get out of bed lately and nothing feels worth it.' -> language a profiler could read as low mood.",
    ),
    Category(
        id="sexuality_gender",
        name="Sexuality and gender identity",
        tier="D",
        source_scope="user_messages",
        description="Sexual orientation or gender identity, stated or implied.",
        example="'How do I tell my parents about my boyfriend?' from a male user.",
    ),
    Category(
        id="religion_beliefs",
        name="Religion and beliefs",
        tier="D",
        source_scope="user_messages",
        description="Religious affiliation, observance, or spiritual practice.",
        example="'What can I meal-prep for suhoor?' -> observant Muslim.",
    ),
    Category(
        id="political_views",
        name="Political views",
        tier="D",
        source_scope="user_messages",
        description="Party leaning, ideology, or position on contested policy.",
        example="Asks for arguments to use at a specific protest.",
    ),
    Category(
        id="ethnicity_origin",
        name="Ethnicity, nationality, or migration status",
        tier="D",
        source_scope="user_messages",
        description="Ethnic background, nationality, or immigration situation.",
        example="'How long does the residence permit renewal take?' -> non-EU resident.",
    ),
    Category(
        id="criminal_or_legal",
        name="Legal exposure",
        tier="D",
        source_scope="user_messages",
        description="Criminal record, ongoing legal trouble, or involvement with authorities.",
        example="'What happens at a first hearing for a DUI?'",
    ),
    Category(
        id="trade_union_activity",
        name="Trade union or labour organising",
        tier="D",
        source_scope="user_messages",
        description="Union membership or workplace organising activity. Explicitly protected under GDPR Article 9.",
        example="'How do I start a works council without HR finding out?'",
    ),
]


# ---------------- helpers used by the prompt and the backend ----------------

VALID_IDS = {c.id for c in CATEGORIES}
CATEGORY_BY_ID = {c.id: c for c in CATEGORIES}


def render_categories_for_prompt(include_tiers: list[str] | None = None) -> str:
    """
    Render the taxonomy for injection into {CATEGORY_BLOCK} in the system prompt.

    Pass include_tiers to build a reduced prompt. Per the prompt notes, when the
    export has no timestamps, call this excluding "M" so the model is not tempted
    to invent metadata it cannot see.
    """
    tiers = include_tiers or TIER_ORDER
    lines: list[str] = []
    for tier in tiers:
        lines.append(f"\nTIER {tier}: {TIER_NAMES[tier]}")
        for cat in (c for c in CATEGORIES if c.tier == tier):
            lines.append(
                f"  - {cat.id} ({cat.name}) [evidence must come from: {cat.source_scope}]: "
                f"{cat.description} Example: {cat.example}"
            )
    return "\n".join(lines)


def canonical_tier(category_id: str) -> str:
    """Validation step 2: the authoritative tier, overriding whatever the model said."""
    return CATEGORY_BY_ID[category_id].tier


def expected_scope(category_id: str) -> str:
    """Validation step 6: where this category's evidence must come from."""
    return CATEGORY_BY_ID[category_id].source_scope


def leakage_score(findings: list[dict]) -> int:
    """
    Tier-weighted score over kept (self, non-fabricated) findings.
    Tier S contributes zero by design. Uses the authoritative tier, not the
    model-reported one.
    """
    return sum(
        TIER_WEIGHTS[canonical_tier(f["category_id"])]
        for f in findings
        if f["category_id"] in VALID_IDS
    )
