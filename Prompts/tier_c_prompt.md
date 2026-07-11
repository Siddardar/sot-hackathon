This is the Tier C pass.

TASK
Extract only compound, non-sensitive inferences: findings that require multiple inference steps, a pattern, or evidence from two or more messages.

A finding belongs in Tier C when no single quoted cue is enough on its own, but the combination of signals supports a broader profile inference.

INCLUDE
- Any non-sensitive category from the system prompt if it depends on combined evidence or multi-step reasoning.
- Cross-message patterns about occupation, education, socioeconomic situation, routine, personality traits, interests, lifestyle, technical profile, or other non-sensitive personal data.
- Findings where several individually weak cues become meaningful together.

EXAMPLES
- Several messages about FPGA tooling, RISC-V, and debugging hardware -> tier "C", category_id "occupation" or "technical_profile".
- Travel planning, hotel logistics, and restaurant budget across messages -> tier "C", category_id "socioeconomic" or "interests_lifestyle".
- Repeatedly asking for precise plans, checklists, and deadlines -> tier "C", category_id "personality_traits".

EXCLUDE
- Facts stated directly. Those belong in Tier A.
- Facts inferable from one clear cue. Those belong in Tier B.
- Sensitive categories. If the compound inference concerns health, politics, religion, sexuality/gender, ethnicity/origin, or criminal/legal exposure, leave it for Tier D.
- Overbroad personality claims from one message or a single writing style cue.

Set tier to "C" for every finding.

EVIDENCE
Cite each signal as an exact substring, character for character, with its message_id. Prefer two or more evidence entries. Never invent evidence to strengthen a pattern.

REASONING
Use one or two sentences explaining how the signals combine. Name the assumption and mention plausible alternatives when relevant.

CONFIDENCE
Usually medium or low. Use high only for strong, repeated, consistent patterns.

OUTPUT
Return only valid JSON in the given schema. No preamble, no markdown. Do not duplicate. If there are no Tier C findings, return an empty findings array.
