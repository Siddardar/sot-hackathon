# Memory Leak — Project Plan

**One-line pitch:** Users upload a chat transcript they had with an AI assistant (ChatGPT / Claude / Gemini export, or a generic JSON). The tool returns a *dossier* of everything a profiler-LLM can infer about them from that conversation, with every inference linked back to the exact sentence that leaked it.

**Why it matters (ties to grading criteria):**
- **Well-grounded problem:** users treat AI chats as ephemeral small talk; providers, third parties, and adversaries can profile deeply from them.
- **Beyond SOTA:** no public tool operationalizes conversational leakage as an interactive, evidence-linked dossier. Existing PII tools flag names and emails; this exposes *inferred* attributes (income class, health status, relationships, political leanings).
- **Ethical core:** the taxonomy is grounded in GDPR Article 9 sensitive categories + a self-defined inference-depth hierarchy. Report discusses the risk of the profiler itself over-inferring — which *is* a finding.
- **Original contribution:** the leakage taxonomy, the evidence-linking JSON schema, the human-validated sample, and the analysis are all human work. The LLM is only an extraction engine.

---

## 1. User flow (v1 — upload-based)

1. User lands on the page, sees a one-screen consent notice ("This tool will attempt to infer personal information from a chat transcript you upload. Do not upload someone else's chat.")
2. User uploads a JSON file. Supported:
   - ChatGPT export (`conversations.json` — array of conversations with `mapping` tree)
   - Claude export (`conversations.json` — array with `chat_messages`)
   - Generic format: `[{"role": "user"|"assistant", "content": "..."}]`
3. If the file has multiple conversations, user picks one from a dropdown (title + first message preview).
4. Backend normalizes to a canonical transcript, sends it to the profiler-LLM, streams results back.
5. Frontend renders the dossier grouped by category, with confidence bars.
6. User clicks any inference → the source sentences highlight in the transcript pane on the right.
7. Optional: "Redact & rerun" — user selects sentences to mask; backend reruns the profiler on the masked transcript and shows a diff dossier ("what you'd have leaked if you hadn't said this").

---

## 2. Architecture

```
┌─────────────────────┐        ┌────────────────────────┐        ┌──────────────────┐
│   Frontend (React)  │──HTTP──▶│   Backend (FastAPI)   │──HTTPS─▶│  Anthropic API   │
│   - Upload          │        │   - /parse             │        │  (profiler LLM)  │
│   - Transcript view │        │   - /analyze (SSE)     │        └──────────────────┘
│   - Dossier + links │◀──SSE──│   - /redact_rerun      │
└─────────────────────┘        │   - taxonomy.py        │
                               │   - normalizers/       │
                               └────────────────────────┘
```

No database needed for v1 — everything is stateless per-request. Transcripts are held in memory for the request lifetime only; the consent screen states this.

---

## 3. Backend

### 3.1 Stack
- **Python 3.11 + FastAPI** — fast to build, good streaming support.
- **Anthropic SDK** (or OpenAI SDK — pick whichever your team has credits for; the code is nearly identical). Recommend Claude for the profiler because structured JSON output is reliable.
- **Pydantic** for schema validation of both incoming payloads and LLM output.
- **uvicorn** to run.

### 3.2 Folder layout
```
backend/
├── main.py                # FastAPI app + routes
├── normalizers/
│   ├── chatgpt.py         # Parses ChatGPT export → canonical
│   ├── claude.py          # Parses Claude export → canonical
│   └── generic.py         # Parses simple {role, content} arrays
├── profiler.py            # Builds prompts, calls LLM, validates output
├── taxonomy.py            # The leakage taxonomy (categories + descriptions)
├── schemas.py             # Pydantic models for API + LLM output
└── prompts/
    └── profiler_system.md # System prompt for the profiler LLM
```

### 3.3 Canonical transcript format
Every uploaded file is normalized to:
```json
{
  "conversation_id": "abc123",
  "title": "Weekend trip planning",
  "messages": [
    {"id": "m0", "role": "user", "content": "...", "timestamp": "..."},
    {"id": "m1", "role": "assistant", "content": "...", "timestamp": "..."}
  ]
}
```
Each message gets a stable `id` so the frontend can highlight it later.

### 3.4 API endpoints

**`POST /parse`**
- Body: uploaded file (multipart) + declared format (or `auto`).
- Returns: list of conversations (id, title, message_count, preview) so the user can pick one.

**`POST /analyze`**
- Body: `{conversation_id, messages: [...canonical]}`.
- Returns: **Server-Sent Events** streaming the dossier as it's generated. Streaming matters for demo feel — findings appear one by one instead of a 15-second blank screen.
- Each event is one inference object (see schema in §3.6).

**`POST /redact_rerun`**
- Body: `{messages, redacted_message_ids: [...]}` (or per-message character ranges for finer control).
- Backend replaces redacted spans with `[REDACTED]` and reruns the profiler.
- Returns: new dossier + diff summary vs. original.

### 3.5 Leakage taxonomy (`taxonomy.py`)

This is the intellectual core — spend real time on it. Suggested categories:

**Tier A — Explicit disclosures** (user stated it outright)
- `identity_direct` — name, age, employer stated
- `location_direct` — city, address stated
- `contact_direct` — phone, email, handles

**Tier B — Direct inferences** (one obvious step)
- `location_inferred` — "the tram to campus" → lives in a city with trams + is a student
- `occupation_inferred` — jargon patterns, schedule mentions
- `relationships` — partner, kids, parents mentioned or implied
- `daily_routine` — sleep, work hours, commute

**Tier C — Compound inferences** (multi-signal profiling)
- `socioeconomic` — spending patterns, vocabulary, holiday destinations
- `education_level` — writing style, references
- `personality_traits` — Big-Five-ish signals, communication style

**Tier D — Sensitive (GDPR Article 9)**
- `health_physical` — symptoms, medication, conditions
- `health_mental` — mood signals, therapy, medication
- `sexuality_gender`
- `religion_beliefs`
- `political_views`
- `ethnicity_origin`
- `criminal_or_legal`

Each category in code carries: id, human name, tier, short description, example. The prompt is generated *from* this list, so adding a category = editing one file.

### 3.6 LLM output schema (`schemas.py`)

```python
class Inference(BaseModel):
    category_id: str            # matches taxonomy
    tier: Literal["A", "B", "C", "D"]
    claim: str                  # short natural-language inference
    confidence: Literal["low", "medium", "high"]
    evidence: list[Evidence]    # sentences it was derived from
    reasoning: str              # 1–2 sentences: how it was inferred

class Evidence(BaseModel):
    message_id: str
    quote: str                  # exact substring from that message
```

Backend validates that every `quote` actually appears in the referenced message. **Reject and retry** any inference that fails this check — this is your guard against the profiler hallucinating evidence, and it's an honest thing to report on.

### 3.7 Profiler prompt (sketch — refine on day 1)

System prompt:
> You are a privacy auditor. Given a transcript of a conversation between a user and an AI assistant, extract everything that could be inferred about the *user* by a data broker or adversary. You return only JSON matching the provided schema. For every inference, quote the exact sentence(s) from the user's messages that support it. Never invent evidence. If uncertain, mark confidence "low". Do not infer things about the assistant. Categories: {injected from taxonomy}. Return between 5 and 40 inferences.

User prompt: the canonical transcript, with user messages tagged by `message_id`.

Ask for JSON mode or use tool-calling to force schema compliance.

### 3.8 Validation script (offline, for the report)
Write a small script that takes ~10 test transcripts (some you write, some real ones team members consent to share) and:
- Runs the profiler.
- Team members manually label each inference as {correct, over-inferred, wrong}.
- Produces precision by tier + a confusion analysis for the report.

This is your empirical result section. Even N=10 with per-inference labels gives you a real number.

---

## 4. Frontend

### 4.1 Stack
- **React + Vite** (or Next.js if the team prefers). Vite is faster to spin up for a 3-day build.
- **TailwindCSS** for styling — no time to hand-write CSS.
- **shadcn/ui** for pre-built components (dialog, card, progress bar).
- **`react-markdown`** for rendering message content safely.
- **EventSource API** for consuming the SSE stream from `/analyze`.

### 4.2 Screens

**Screen 1 — Consent & upload**
- Full-page card. Plain-language consent text. Checkbox "I confirm this is my own chat."
- Drag-and-drop file input. Format auto-detect + manual override dropdown.

**Screen 2 — Conversation picker** (only if the upload has >1 conversation)
- List of conversations with title, message count, first-message preview. User clicks one.

**Screen 3 — Analysis (the main view)** — two-pane layout:

*Left pane (60%): Dossier*
- Grouped by tier (A → D), collapsible sections.
- Each inference card shows: category badge, claim, confidence bar, "reasoning" tooltip, and a small "N sources" chip.
- Cards appear one-by-one as the SSE stream delivers them (with a subtle fade-in — this makes the demo feel alive).
- A running "leakage score" at the top: `count × tier_weight`, animated as new inferences arrive.

*Right pane (40%): Transcript*
- Full conversation, user messages visually distinct from assistant.
- When user clicks an inference card, the referenced sentences get highlighted (yellow) and the pane scrolls to the first one. Multiple clicks accumulate highlights; a "clear" button resets.

**Screen 4 — Redaction mode** (button in top bar)
- Transcript pane becomes selectable — user clicks sentences to mark for redaction.
- "Rerun with redactions" button hits `/redact_rerun`.
- Dossier pane splits: original findings (greyed out if now missing) vs. new findings. A summary line: "Redacting 3 sentences eliminated 7 inferences, including 2 sensitive-tier."

### 4.3 State management
No Redux needed. `useState` + `useReducer` for the dossier list. One custom hook `useAnalysisStream(conversation)` that opens the EventSource and appends inferences.

### 4.4 Demo-quality details worth the time
- Smooth stagger animation on inference cards (200ms delay each).
- The "leakage score" ticker.
- On highlight, the transcript sentence gets an underline + a small floating badge showing which inference it produced.
- Dark mode toggle — presentations often happen in dark rooms and it screenshots better.

---

## 5. Three-day plan

### Day 1 — Skeleton + taxonomy
| Time | Backend | Frontend | Ethics/Research |
|---|---|---|---|
| AM | FastAPI scaffold; `/parse` for one format (Claude export) | Vite + Tailwind scaffold; upload screen; consent screen | Draft taxonomy v1 (categories + descriptions) |
| PM | First profiler call working end-to-end with a hardcoded transcript; schema validation | Transcript view + dumb dossier (no styling) rendering from a mocked API | Write 3–5 hand-crafted test transcripts covering all tiers |

**End-of-day-1 goal:** you can upload a Claude export, pick a conversation, and see a rough JSON dossier appear.

### Day 2 — Real analysis + polish
| Time | Backend | Frontend | Ethics/Research |
|---|---|---|---|
| AM | Add ChatGPT + generic normalizers; SSE streaming from `/analyze`; evidence-quote validation | Two-pane layout; click-to-highlight interaction; card styling; SSE consumer | Team labels the 5 test transcripts by hand → seed evaluation set |
| PM | `/redact_rerun` endpoint | Redaction mode UI; leakage score ticker; animations | Draft ethics section of the report |

**End-of-day-2 goal:** the whole loop works. Highlighting works. Redaction rerun works. Someone unfamiliar could use it.

### Day 3 — Evaluation, report, presentation
| Time | Backend | Frontend | Ethics/Research |
|---|---|---|---|
| AM | Run profiler on 10 consented transcripts; freeze prompt | Bug fixes; dark mode; make it look good | Manually label all inferences → precision numbers by tier |
| PM | Package for demo (Dockerfile or just run scripts) | Prepare a "safe" demo transcript so live demo can't leak a real teammate | Write report (10 pages) + build slides + GenAI usage log |

---

## 6. Ethics section (bullet points for the report)

- **Consent-design trade-off:** the punch of the tool depends on the user not knowing exactly *what* will be extracted. Mitigation: upfront explanation of categories at a high level; opt-in checkbox; local-only processing framing.
- **Third-party data:** uploaded chats often contain information about *other* people (a friend the user mentioned). We do not profile these third parties. State this in the prompt and the consent screen.
- **Profiler over-inference risk:** the extractor can hallucinate traits. Mitigated by: evidence-quoting requirement, backend rejection of ungrounded quotes, manual precision audit. Residual over-inference is itself part of the finding — this is what real data brokers also do, incorrectly.
- **Dual-use:** the same pipeline could be used maliciously. Report addresses this directly and argues for the tool as a demonstration + open-source educational artifact rather than a hosted service.
- **Data handling:** no logging of transcripts server-side; no persistence; API keys server-side only; suggested local deployment for anyone actually using it.

---

## 7. Beyond v1 (mention in report as future work)

- Live-chat mode with the leakage score updating per turn (originally proposed version).
- Multi-model comparison: run the same transcript through 3 profilers, show which inferences all models converge on (higher-confidence findings).
- Localization: does leakage differ across languages? Non-English chats may leak more due to weaker refusal training.
- A browser extension that runs on your active ChatGPT/Claude tab.

---

## 8. Stack summary (for the "tech stack" slide)

- **Frontend:** React 18, Vite, TailwindCSS, shadcn/ui, EventSource
- **Backend:** Python 3.11, FastAPI, Pydantic, Anthropic SDK (or OpenAI)
- **LLM:** Claude Sonnet (recommended) for the profiler; JSON-mode / tool-calling for schema compliance
- **Infra:** local dev only for the hackathon; single `docker-compose up` for the demo machine
