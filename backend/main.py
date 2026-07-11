"""FastAPI app for Memory Leak.

Endpoints
---------
* ``POST /parse``         — upload an export, get canonical conversations back.
* ``POST /analyze``       — stream a dossier for one conversation (SSE).
* ``POST /redact_rerun``  — re-profile a masked transcript and diff vs. original.
* ``GET  /test_gemini``   — make a minimal real Gemini API call.
* ``GET  /health``        — liveness/readiness probe.

The app is stateless: transcripts live only for the lifetime of a request.
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from typing import Any, Iterator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import profiler
from normalizers import (
    UnsupportedFormatError,
    normalize,
    parse_memories,
    parse_users,
    to_user_only,
)
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


def _find_zip_member(zf: zipfile.ZipFile, basename: str) -> Optional[str]:
    """Return the shallowest archive member whose filename is ``basename``.

    Claude exports may be zipped with a top-level folder prefix and also contain
    per-project/design conversation files in subfolders — we want the top-level
    ``conversations.json`` / ``users.json``, i.e. the one nearest the root.
    """
    candidates = [
        name for name in zf.namelist()
        if not name.endswith("/") and name.rsplit("/", 1)[-1] == basename
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda name: name.count("/"))


def _read_optional_member(zf: zipfile.ZipFile, basename: str) -> Optional[Any]:
    """Read and JSON-parse an optional top-level member; return None if absent/malformed."""
    member = _find_zip_member(zf, basename)
    if member is None:
        return None
    try:
        return json.loads(zf.read(member))
    except json.JSONDecodeError:
        return None


def _load_export(raw: bytes) -> tuple[Any, Optional[Any], Optional[Any]]:
    """Return ``(conversations_data, users_data, memories_data)`` from an upload.

    Accepts either the full account export as a ``.zip`` (we pull the top-level
    ``conversations.json``, ``users.json``, and ``memories.json`` out of it) or a
    single ``conversations.json`` file (in which case users/memories are None).
    """
    bio = io.BytesIO(raw)
    if zipfile.is_zipfile(bio):
        with zipfile.ZipFile(bio) as zf:
            conv_member = _find_zip_member(zf, "conversations.json")
            if conv_member is None:
                raise HTTPException(
                    status_code=422,
                    detail="No conversations.json found in the uploaded archive.",
                )
            try:
                conversations_data = json.loads(zf.read(conv_member))
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"conversations.json is not valid JSON: {exc}") from exc

            users_data = _read_optional_member(zf, "users.json")
            memories_data = _read_optional_member(zf, "memories.json")
            return conversations_data, users_data, memories_data

    try:
        return json.loads(raw), None, None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: {exc}") from exc


# --------------------------------------------------------------------------- #
# /parse
# --------------------------------------------------------------------------- #
async def _read_json_upload(upload: Optional[UploadFile]) -> Optional[Any]:
    """Read and JSON-parse an optional uploaded file part; None if absent/malformed."""
    if upload is None:
        return None
    raw = await upload.read()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@app.post("/parse", response_model=ParseResponse)
async def parse(
    file: UploadFile = File(...),
    format: str = Form("auto"),
    human_only: bool = Form(True),
    users: Optional[UploadFile] = File(None),
    memories: Optional[UploadFile] = File(None),
) -> ParseResponse:
    """Parse an uploaded export into canonical conversations.

    Body: multipart with ``file`` (a ``.zip`` account export or a single
    ``conversations.json``), optional ``format`` (``auto`` | ``claude`` |
    ``chatgpt`` | ``generic``), optional ``human_only`` (default ``true`` — keep
    only the user's messages), and optional ``users``/``memories`` file parts
    (used by the "folder" upload path, which sends the three JSONs separately).
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    conversations_data, users_data, memories_data = _load_export(raw)

    # Separately-uploaded parts (folder mode) fill in anything the main file lacked.
    if users_data is None:
        users_data = await _read_json_upload(users)
    if memories_data is None:
        memories_data = await _read_json_upload(memories)

    try:
        used_format, conversations = normalize(conversations_data, format)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if human_only:
        conversations = to_user_only(conversations)
        if not conversations:
            raise HTTPException(status_code=422, detail="No human messages found to analyze.")

    account = parse_users(users_data) if users_data is not None else None
    memory = parse_memories(memories_data) if memories_data is not None else None

    summaries = [
        ConversationSummary(
            conversation_id=conv.conversation_id,
            title=conv.title,
            message_count=len(conv.messages),
            preview=_preview(conv.messages[0].content) if conv.messages else "",
        )
        for conv in conversations
    ]

    return ParseResponse(
        format=used_format,
        conversations=conversations,
        summaries=summaries,
        account=account,
        memory=memory,
    )


# --------------------------------------------------------------------------- #
# /analyze  (Server-Sent Events)
# --------------------------------------------------------------------------- #
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _analyze_stream(request: AnalyzeRequest) -> Iterator[str]:
    """Yield SSE events: one ``inference`` per finding, then ``done``.

    Runs the (blocking) profiler once; findings are emitted one at a time so the
    UI can stagger them in. This is a sync generator so FastAPI runs it in a
    worker thread and the blocking Gemini call doesn't stall the event loop.
    """
    try:
        result = profiler.run_profiler(request.messages, mode=request.mode)
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
            "mode": result.mode,
            "mock": result.mock,
            "tier_counts": result.tier_counts,
            "tier_errors": result.tier_errors,
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
@app.get("/test_gemini")
def test_gemini(
    prompt: str = Query(
        "Reply with exactly: Gemini API test ok",
        min_length=1,
        max_length=500,
    ),
) -> dict:
    """Verify the Gemini SDK/API key/model with a small real generation."""
    try:
        return profiler.test_gemini_api(prompt)
    except profiler.ProfilerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": profiler.MODEL,
        "mock_mode": profiler.use_mock(),
        "api_key_configured": profiler.api_key_configured(),
    }


@app.get("/")
def root() -> dict:
    return {"name": "Glasshouse", "endpoints": ["/parse", "/analyze", "/redact_rerun", "/test_gemini", "/health"]}
