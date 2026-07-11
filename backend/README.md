# Memory Leak — Backend

FastAPI service that normalizes an uploaded chat export and returns a
privacy-leakage dossier from a profiler LLM (Claude), with every inference
linked to the exact sentence that leaked it.

## Run

```bash
cd backend
python3 -m venv venv                 # (already created)
./venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # required for /analyze and /redact_rerun
./venv/bin/uvicorn main:app --reload --port 8000
```

Config lives in env vars — see `.env.example`.

## Endpoints

| Method | Path             | Body | Returns |
|--------|------------------|------|---------|
| POST   | `/parse`         | multipart: `file` (JSON export) + `format` (`auto`\|`claude`\|`chatgpt`\|`generic`) | `{format, conversations[], summaries[]}` |
| POST   | `/analyze`       | `{conversation_id?, messages[]}` | **SSE stream** — `meta`, one `inference` per finding, then `done` (`error` on failure) |
| POST   | `/redact_rerun`  | `{messages[], redacted_message_ids[], redactions[]?, original_inferences[]?}` | `{inferences[], diff}` |
| GET    | `/health`        | — | `{status, model, api_key_configured}` |

The canonical transcript and dossier schemas are defined in `schemas.py`.

## SSE format (`/analyze`)

```
event: meta
data: {"count": 12, "model": "claude-opus-4-8", "dropped_evidence": 1, "dropped_inferences": 0}

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
