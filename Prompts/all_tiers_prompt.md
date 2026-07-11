This is the full report pass.

TASK
Extract the most important personal-data findings across all tiers in one coherent report. Choose exactly one best tier for each finding. Do not return the same underlying personal fact more than once.

TIER SELECTION
- Tier A: the person stated the fact outright. The quoted words themselves reveal the fact.
- Tier B: the fact is one obvious inference step from one cue in one message.
- Tier C: the fact requires multiple inference steps, a repeated pattern, or evidence from two or more messages.
- Tier D: the finding is sensitive personal data. Sensitivity overrides derivation distance, so use Tier D for sensitive facts whether they are explicit, one-step, or compound.

CATEGORY SELECTION
Use any category id from the system prompt. Category and tier are independent except that sensitive category ids must always use Tier D.

Non-sensitive categories may appear in Tier A, B, or C depending on how the finding was derived. For example, occupation is Tier A if the person directly says their job, Tier B if one message strongly implies their field, and Tier C if several weaker signals combine into a broader profile.

Sensitive category ids must always be Tier D:
- health_physical
- health_mental
- sexuality_gender
- religion_beliefs
- political_views
- ethnicity_origin
- criminal_or_legal

DEDUPLICATION
Return a concise report, not four overlapping reports merged together.

If the same personal fact could fit multiple tiers, choose the strongest correct tier:
- Use Tier D if the fact is sensitive.
- Otherwise use Tier A if the fact is explicitly stated.
- Otherwise use Tier B if one clear cue supports it.
- Otherwise use Tier C for broader pattern-based findings.

Do not split one fact into several near-duplicates with slightly different wording. Prefer one clear finding with the best category and strongest evidence.

EXAMPLES
- "I live in Munich" -> tier "A", category_id "location".
- "I work as a nurse" -> tier "A", category_id "occupation".
- "My daughter's school called" -> tier "B", category_id "relationships", because it implies the person is a parent.
- "Can you make this work on my MacBook?" -> tier "B", category_id "technical_profile", because it implies device/OS use.
- Several messages about FPGA tooling, RISC-V, and debugging hardware -> tier "C", category_id "occupation" or "technical_profile".
- Repeatedly asking for precise plans, checklists, and deadlines -> tier "C", category_id "personality_traits".
- "I have diabetes" -> tier "D", category_id "health_physical".
- "My therapist said..." -> tier "D", category_id "health_mental".

EVIDENCE
Quote exact substrings from the person's messages only, copied character for character with message_id.

For Tier A, the quote must contain the stated fact.
For Tier B, quote the single cue the inference rests on.
For Tier C, include the multiple cues or pattern signals.
For Tier D, quote exactly what supports the sensitive exposure.

REASONING
Use one or two sentences. State whether the finding is explicit, one-step, compound, or sensitive. Name the cue, pattern, assumption, or proxy used. For weak or speculative findings, mention plausible alternatives.

OUTPUT
Return only valid JSON in the given schema. No preamble, no markdown. If there are no findings, return an empty findings array.
