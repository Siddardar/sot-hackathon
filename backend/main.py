"""FastAPI app for Memory Leak.

Endpoints
---------
* ``POST /parse``         — upload an export, get canonical conversations back.
* ``POST /analyze``       — stream a dossier for one conversation (SSE).
* ``POST /redact_rerun``  — re-profile a masked transcript and diff vs. original.
* ``GET  /health``        — liveness/readiness probe.

The app is stateless: transcripts live only for the lifetime of a request.
"""

from __future__ import annotations

import json
import os
import time
from typing import Iterator, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import profiler
from normalizers import UnsupportedFormatError, normalize
from schemas import (
    AnalyzeRequest,
    ConversationSummary,
    ParseResponse,
    RedactRerunRequest,
    RedactRerunResponse,
)

app = FastAPI(title="Memory Leak", version="1.0.0")

# Wide-open CORS for local dev (Vite frontend on a different port).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Small per-card delay so the dossier "fades in" during the demo. Set to 0 to disable.
STREAM_DELAY_SECONDS = float(os.environ.get("STREAM_DELAY_SECONDS", "0.15"))

_PREVIEW_CHARS = 140


def _preview(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _PREVIEW_CHARS else text[: _PREVIEW_CHARS - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# /parse
# --------------------------------------------------------------------------- #
@app.post("/parse", response_model=ParseResponse)
async def parse(
    file: UploadFile = File(...),
    format: str = Form("auto"),
) -> ParseResponse:
    """Parse an uploaded export into canonical conversations.

    Body: multipart with ``file`` (the JSON export) and optional ``format``
    (``auto`` | ``claude`` | ``chatgpt`` | ``generic``).
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: {exc}") from exc

    try:
        used_format, conversations = normalize(data, format)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    summaries = [
        ConversationSummary(
            conversation_id=conv.conversation_id,
            title=conv.title,
            message_count=len(conv.messages),
            preview=_preview(conv.messages[0].content) if conv.messages else "",
        )
        for conv in conversations
    ]

    return ParseResponse(format=used_format, conversations=conversations, summaries=summaries)


# --------------------------------------------------------------------------- #
# /analyze  (Server-Sent Events)
# --------------------------------------------------------------------------- #
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _analyze_stream(request: AnalyzeRequest) -> Iterator[str]:
    """Yield SSE events: one ``inference`` per finding, then ``done``.

    Runs the (blocking) profiler once; findings are emitted one at a time so the
    UI can stagger them in. This is a sync generator so FastAPI runs it in a
    worker thread and the blocking Anthropic call doesn't stall the event loop.
    """
    try:
        result = profiler.run_profiler(request.messages)
    except profiler.ProfilerError as exc:
        yield _sse("error", {"message": str(exc)})
        yield _sse("done", {"count": 0})
        return
    except Exception as exc:  # noqa: BLE001 — surface any failure to the client cleanly
        yield _sse("error", {"message": f"Unexpected profiler error: {exc}"})
        yield _sse("done", {"count": 0})
        return

    yield _sse(
        "meta",
        {
            "count": len(result.inferences),
            "model": result.model,
            "dropped_evidence": result.dropped_evidence,
            "dropped_inferences": result.dropped_inferences,
        },
    )

    for inference in result.inferences:
        yield _sse("inference", json.loads(inference.model_dump_json()))
        if STREAM_DELAY_SECONDS > 0:
            time.sleep(STREAM_DELAY_SECONDS)

    yield _sse("done", {"count": len(result.inferences)})


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> StreamingResponse:
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages to analyze.")
    return StreamingResponse(
        _analyze_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so events flush immediately
        },
    )


# --------------------------------------------------------------------------- #
# /redact_rerun
# --------------------------------------------------------------------------- #
@app.post("/redact_rerun", response_model=RedactRerunResponse)
def redact_rerun(request: RedactRerunRequest) -> RedactRerunResponse:
    """Re-profile a masked transcript and diff it against the original dossier."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages to analyze.")
    if not request.redacted_message_ids and not request.redactions:
        raise HTTPException(status_code=400, detail="No redactions were provided.")

    masked = profiler.mask_messages(
        request.messages,
        request.redacted_message_ids,
        request.redactions,
    )

    try:
        result = profiler.run_profiler(masked)
    except profiler.ProfilerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    diff = profiler.diff_dossiers(request.original_inferences, result.inferences)
    return RedactRerunResponse(inferences=result.inferences, diff=diff)


# --------------------------------------------------------------------------- #
# Health / root
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": profiler.MODEL,
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.get("/")
def root() -> dict:
    return {"name": "Memory Leak", "endpoints": ["/parse", "/analyze", "/redact_rerun", "/health"]}
