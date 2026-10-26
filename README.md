# REDELIVER — Voice Assistant for Parcel Redelivery

A backend for a phone-line voice assistant that helps callers who missed a
parcel delivery.  The caller provides a tracking ID, verifies their identity,
and then reschedules delivery, picks a collection point, cancels, or checks
status — all handled by a rule-based brain written in plain Python (no LLM).

## Quick start

```bash
# 1. Clone and enter the repo
cd backend

# 2. Create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit the env file
cp ../.env.example ../.env   # adjust values if needed

# 5. Run the dev server
uvicorn app.main:app --reload --port 8000

# 6. Verify it works
curl http://localhost:8000/health
# → {"status":"ok","version":"1.0.0"}
```

## Run tests

```bash
cd backend
pytest -v
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

## API endpoints (implemented so far)

| Method | Path      | Description          |
|--------|-----------|----------------------|
| GET    | `/health` | Health check + version |

*More endpoints will be added as the build progresses.*

## Project structure

```
backend/
├── app/
│   ├── api/routes/     # FastAPI route modules
│   ├── brain/          # Intent detection, state machine, NLP (coming)
│   ├── core/           # Config and logging
│   ├── data/           # Data loading and repository (coming)
│   ├── models/         # Pydantic models (coming)
│   └── services/       # Business logic (coming)
├── data/               # Fake JSON data files (coming)
└── tests/              # pytest suite
```

## Key rules

- **No LLM in the brain.** All decision-making is plain Python code.
- **No real personal data.** All parcels, names, and phone numbers are fake.
- **No secrets in the repo.** Use `.env` for configuration.
