# Memory Leak — Backend

FastAPI service that normalizes an uploaded chat export and returns a
privacy-leakage dossier from a profiler LLM (Gemini), with every inference
linked to the exact sentence that leaked it.

## Run

```bash
cd backend
python3 -m venv venv                 # (already created)
./venv/bin/pip install -r requirements.txt
export GOOGLE_API_KEY=...             # or GEMINI_API_KEY; required for real /analyze and /redact_rerun
./venv/bin/uvicorn main:app --reload --port 8000
```

Config lives in env vars — see `.env.example`.

### End-to-end with the frontend (mock mode)

No API key needed to test the wiring. With `GOOGLE_API_KEY` / `GEMINI_API_KEY` unset, the
profiler auto-runs in **mock mode** and returns a grounded sample dossier.

```bash
# terminal 1 — backend on :8000 (mock mode, no key required)
cd backend && ./venv/bin/uvicorn main:app --reload --port 8000

# terminal 2 — frontend on :3000
cd frontend && npm run dev
```

Open the app, click **Upload a conversation**, and pick the Claude export
(ZIP, a single `conversations.json`, or the export Folder). The frontend POSTs
to `/parse`, then streams `/analyze`, and **logs everything to the browser
console** (`[Glasshouse] …`): the parse result, `account` (users.json), provider
`memory` (memories.json), each streamed inference, and the full dossier. The
`meta` event carries `mock: true` so you can tell sample output apart from real.

Point the frontend at a non-default backend with `NEXT_PUBLIC_API_BASE`
(defaults to `http://localhost:8000`).

The real profiler uses the Gemini SDK. Set `PROFILER_MODEL` to override the
default model (`gemini-3.5-flash`).

## Endpoints

| Method | Path             | Body | Returns |
|--------|------------------|------|---------|
| POST   | `/parse`         | multipart: `file` (a `.zip` account export **or** a single `conversations.json`) + `format` (`auto`\|`claude`\|`chatgpt`\|`generic`) + `human_only` (default `true`) | `{format, conversations[], summaries[], account?, memory?}` |
| POST   | `/analyze`       | `{conversation_id?, messages[]}` | **SSE stream** — `meta`, one `inference` per finding, then `done` (`error` on failure) |
| POST   | `/redact_rerun`  | `{messages[], redacted_message_ids[], redactions[]?, original_inferences[]?}` | `{inferences[], diff}` |
| GET    | `/test_gemini`   | optional query: `prompt` | `{ok, model, text}` from a minimal real Gemini call |
| GET    | `/health`        | — | `{status, model, mock_mode, api_key_configured}` |

The canonical transcript and dossier schemas are defined in `schemas.py`.

### Upload handling

A Claude account export is a `.zip` containing `conversations.json`, `users.json`,
`memories.json`, `projects/`, and `design_chats/`. `/parse` uses the top-level
`conversations.json`, `users.json`, and `memories.json`:

- **`conversations.json`** → canonical conversations. With `human_only=true`
  (default) assistant turns are dropped — the user's own messages are what leak
  their information, and this roughly halves the token count sent to the profiler
  (measured **~78%** fewer characters on a real export). Empty and file-only
  conversations are skipped.
- **`users.json`** → the `account` block (`name`, `email`, `phone`). This is
  ground-truth identity the user gave the provider, so it has no sentence to
  quote; the frontend surfaces it separately as guaranteed Tier-A leakage rather
  than as an evidence-linked inference.
- **`memories.json`** → the `memory` block: the provider's *own* inferred profile
  of the user (`conversations_memory` markdown + per-project `project_memories`).
  This is what the provider already remembers/inferred — surface it as a "what
  the provider already knows about you" panel, distinct from our transcript-derived
  dossier.

You can also upload a bare `conversations.json` (no `account`/`memory` returned).
`projects/` and `design_chats/` are ignored.

## SSE format (`/analyze`)

```
event: meta
data: {"count": 12, "model": "gemini-3.5-flash", "dropped_evidence": 1, "dropped_inferences": 0}

event: inference
data: {"category_id": "...", "tier": "D", "claim": "...", "confidence": "high", "reasoning": "...", "evidence": [{"message_id": "m3", "quote": "..."}]}

event: done
data: {"count": 12}
```

Every evidence `quote` is validated to appear verbatim in the cited message;
ungrounded quotes (and inferences left with no evidence) are dropped before
streaming — this is the guard against the profiler hallucinating evidence.

## Layout

```
backend/
├── main.py            # FastAPI app + routes
├── schemas.py         # Pydantic models (canonical transcript + dossier)
├── profiler.py        # prompt build, LLM call, evidence grounding, redaction diff
├── normalizers/
│   ├── __init__.py    # format auto-detect + dispatch
│   ├── claude.py      # Claude export -> canonical
│   ├── chatgpt.py     # ChatGPT export (mapping tree) -> canonical
│   └── generic.py     # {role, content} arrays -> canonical
├── taxonomy.py        # (owned separately — see below)
└── prompts/
    └── profiler_system.md   # (owned separately — see below)
```

## Interface for `taxonomy.py` and `prompts/` (owned separately)

The profiler reads these if present and falls back to a built-in default
otherwise, so the API runs today. To plug in the real versions:

- **`taxonomy.py`** — expose `TAXONOMY`, a list of categories. Each item may be a
  dict or an object with attributes: `id`, `name`, `tier` (`"A"`–`"D"`),
  `description`, and optional `example`. The system prompt's category list is
  generated from this.
- **`prompts/profiler_system.md`** — the profiler system prompt. Include the
  literal token `{taxonomy}` where the rendered category list should be
  injected; if omitted, the categories are appended to the end.
