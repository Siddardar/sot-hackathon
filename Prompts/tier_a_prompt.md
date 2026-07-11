This is the Tier A pass.

TASK
Extract only explicit, non-sensitive disclosures: facts the person stated outright about themselves. No inference is allowed.

A finding belongs in Tier A when the quoted words themselves reveal the fact. Reading the quote alone should be enough to see the disclosure.

INCLUDE
- Any non-sensitive category from the system prompt if it is stated directly.
- Direct statements of identity, location, contact details, occupation, relationships, routine, education, finances, interests, lifestyle, technical setup, or similar personal data.

EXAMPLES
- "I live in Munich" -> tier "A", category_id "location".
- "I work as a nurse" -> tier "A", category_id "occupation".
- "My wife and I are moving" -> tier "A", category_id "relationships".
- "I am a university student" -> tier "A", category_id "education_level".

EXCLUDE
- Anything requiring even one reasoning step. Put that in Tier B or C.
- Sensitive categories. If the person explicitly states a health, political, religious, sexuality/gender, ethnicity/origin, or criminal/legal fact, leave it for Tier D.
- Facts about the assistant.

Set tier to "A" for every finding.

EVIDENCE
The quoted substring must itself contain the stated fact, copied character for character from one of the person's messages, with its message_id. Do not paraphrase, merge, or invent evidence.

REASONING
Use one sentence. For explicit disclosures, say that the person stated the fact directly.

CONFIDENCE
Usually high. Use medium or low if the statement is hedged, quoted from someone else, hypothetical, or ambiguous.

OUTPUT
Return only valid JSON in the given schema. No preamble, no markdown. Do not duplicate. If there are no Tier A findings, return an empty findings array.
