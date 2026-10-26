# REDELIVER — Parcel Redelivery Assistant

REDELIVER is a Python backend for a missed-delivery assistant. A caller can
verify a parcel using its tracking ID and phone number's last four digits,
then reschedule delivery, choose a pickup point, cancel delivery, or check
parcel status. Intent detection and dialogue decisions use explicit Python
rules; no large language model is used in the decision path.

The backend accepts text transcriptions. Speech recognition, audio playback,
and a frontend are outside this backend phase.

## Quick start

From the repository root, create and activate a virtual environment inside
`backend`, then install dependencies:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate` instead. The
defaults work locally. To customize them, copy `../.env.example` to
`../.env`, then start the API from `backend/`:

```bash
uvicorn app.main:app --reload --port 8000
```

Check `http://localhost:8000/health`. Interactive API documentation is at
`http://localhost:8000/docs`.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health status and application version |
| `POST` | `/sessions` | Start a session and return the greeting |
| `POST` | `/sessions/{session_id}/turns` | Submit a transcript or silence turn |
| `GET` | `/sessions/{session_id}` | Read session state, slots, and conversation history |
| `DELETE` | `/sessions/{session_id}` | End a session |

Create a session, then use its returned `session_id` for each turn:

```json
POST /sessions
{}
```

```json
POST /sessions/{session_id}/turns
{
  "text": "RD30000001",
  "silence": false,
  "stt_confidence": 0.98
}
```

`text` is optional and limited to 2,000 characters. Empty text is treated as
silence. `stt_confidence` is optional; values below `0.5` trigger a re-ask.
The turn response includes the assistant reply, whether the call ended, and a
decision trace. See [docs/BACKEND_GUIDE.md](docs/BACKEND_GUIDE.md) for a full
conversation example and endpoint details.

The Postman collection at
[`docs/postman/redeliver.postman_collection.json`](docs/postman/redeliver.postman_collection.json)
contains the health check and session requests.

## Run tests

From `backend/`:

```bash
python -m pytest tests/ -v
```

With coverage:

```bash
python -m pytest tests/ --cov=app --cov-report=term-missing
```

## Design and data

- The dialogue brain uses weighted keyword/regex matching and an explicit
  state machine in plain Python.
- The repository uses fake parcel and pickup-point records in `backend/data/`.
- Sessions and parcel changes live in memory and reset when the server restarts.
- Delivery slots are generated for a seven-day window using an injected clock.
- No real personal information or credentials belong in the sample data.

Read [DESIGN.md](DESIGN.md) for the decision design and
[AI_USAGE.md](AI_USAGE.md) for the AI tools used during development.
