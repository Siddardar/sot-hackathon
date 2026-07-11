This is the Tier D pass.

TASK
Extract only sensitive personal data. Tier D is defined by sensitivity, not by inference distance. Include sensitive facts whether they are stated outright, inferred in one step, or inferred from multiple messages.

Sensitive findings are high-impact, so precision matters more than volume. Do not stretch. If the evidence does not clearly support a sensitive attribute or sensitive exposure, leave it out.

CATEGORIES
Use only these category ids:
- health_physical: symptoms, diagnoses, medication, disability, pregnancy, medical visits, or physical health status.
- health_mental: mood, therapy, psychiatric medication, distress signals, addiction, or mental-health-related language.
- sexuality_gender: sexual orientation, sexual behavior, gender identity, or gender transition.
- religion_beliefs: religious affiliation, observance, practice, or spiritual belief.
- political_views: party leaning, ideology, activism, voting preference, or position on contested policy.
- ethnicity_origin: ethnicity, nationality, ancestry, migration status, language origin, or protected origin signals.
- criminal_or_legal: criminal record, legal trouble, litigation, immigration enforcement, police contact, or involvement with authorities.

INCLUDE
- Explicit sensitive disclosures.
- One-step sensitive inferences from a clear cue.
- Compound sensitive inferences from multiple cues, if the combination is strong enough.

EXAMPLES
- "I have diabetes" -> tier "D", category_id "health_physical".
- "My therapist said..." -> tier "D", category_id "health_mental".
- "I am voting Green" -> tier "D", category_id "political_views".
- Multiple messages about medication, panic attacks, and therapy appointments -> tier "D", category_id "health_mental".

EXCLUDE
- Non-sensitive findings, even if they are important. Those belong in A, B, or C.
- Medical, political, religious, ethnicity/origin, sexuality/gender, or legal guesses based on thin stereotypes.
- Clinical diagnoses unless the person stated the diagnosis directly.

Set tier to "D" for every finding.

SUBJECT
Sensitive facts about other people are especially not to be profiled. If unavoidable, mark them "third_party", give one line, and stop there.

EVIDENCE
Quote the exact substring the finding rests on, character for character, with its message_id. For compound sensitive findings, include the multiple cues. Never invent evidence for a sensitive claim.

SPECIAL CARE
- For mental health, report only what a profiler could read from the text, never a clinical conclusion.
- Keep every finding to exactly what the evidence supports. Add no operational detail and do not speculate beyond the quote.
- When a sensitive attribute is weakly but plausibly implied, use low confidence only if the evidence is still concrete. Otherwise omit it.

REASONING
Use one or two sentences. State whether the sensitive exposure is explicit, one-step, or compound. Name the cue and the assumption.

CONFIDENCE
Use low, medium, or high honestly. Do not inflate sensitive claims.

OUTPUT
Return only valid JSON in the given schema. No preamble, no markdown. Do not duplicate. If there are no Tier D findings, return an empty findings array.
