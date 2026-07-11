This is the Tier A pass.

TASK
Extract explicit, non-sensitive disclosures: facts the person stated outright about themselves.

A finding belongs in Tier A when the quoted words themselves reveal the fact. Reading the quote alone should show the disclosure without needing an inference.

INCLUDE
- Any non-sensitive category from the system prompt if it is stated directly.
- Direct statements of identity, location, contact details, occupation, relationships, routine, education, finances, interests, lifestyle, technical setup, or similar personal data.

EXAMPLES
- "I live in Munich" -> tier "A", category_id "location".
- "I work as a nurse" -> tier "A", category_id "occupation".
- "My wife and I are moving" -> tier "A", category_id "relationships".
- "I am a university student" -> tier "A", category_id "education_level".

EXCLUDE
- Anything requiring an inference. Put one-step inferences in Tier B and compound inferences in Tier C.
- Sensitive categories. If the person explicitly states a health, political, religious, sexuality/gender, ethnicity/origin, or criminal/legal fact, leave it for Tier D.
- Facts about the assistant.

Set tier to "A" for every finding.

EVIDENCE
The quoted substring must itself contain the stated fact, copied character for character from one of the person's messages, with its message_id.

REASONING
Use one sentence stating that the person disclosed the fact directly.

OUTPUT
Return only valid JSON in the given schema. No preamble, no markdown. Do not duplicate. If there are no Tier A findings, return an empty findings array.
