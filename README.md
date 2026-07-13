# Glasshouse

Glasshouse is a privacy-audit demo for exported AI chat histories. It parses a ChatGPT or Claude export, sends the user's messages to a Gemini-backed profiler, and generates a report showing what could be inferred from those conversations, with evidence quotes linked back to the source transcript.

The app has two parts:

- `frontend/`: Next.js UI for upload, mode selection, export instructions, and report viewing.
- `backend/`: FastAPI service for parsing exports, calling Gemini, validating evidence quotes, and streaming findings.

## Requirements

- Node.js and npm
- Python 3.10+
- A Gemini API key for real analysis

The backend accepts either:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

Without a key, the backend defaults to mock mode so the upload/report flow can still be tested.

## Backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Add your key to `backend/.env`:

```bash
GOOGLE_API_KEY=your_key_here
```

Run the backend:

```bash
./venv/bin/uvicorn main:app --reload --port 8000
```

Useful endpoints:

- `GET /health`
- `GET /test_gemini`
- `POST /parse`
- `POST /analyze`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

By default the frontend talks to:

```text
http://localhost:8000
```

To use another backend URL, set:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## Usage

1. Export your Claude or ChatGPT conversations.
2. Start the backend on port `8000`.
3. Start the frontend on port `3000`.
4. Upload the export `.zip`, export folder, or `conversations.json`.
5. Choose conservative or speculative mode.
6. Generate the report.

Reports are stored locally in the browser using `localStorage`; they are not persisted by the backend.
