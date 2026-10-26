# REDELIVER — Build Progress

> **Purpose:** This file tracks what has been built, what comes next, and
> everything a new agent with no prior context needs to continue the work.
> Read `docs/PLAN.md` for the full design; this file is the execution log.

---

## Project rules (always follow these)

1. **No LLM in the brain.** Intent detection, slot filling, state transitions —
   all plain Python.  `tests/test_no_llm.py` enforces this.
2. **No git commands.** The owner handles version control.
3. **One step at a time.** Write code → write tests → run full suite → all green
   → update docs → move on.
4. **Determinism.** Inject `clock: datetime` (not `date`) everywhere.  Never call
   `datetime.now()` or `date.today()` in app or test code.  Fixture
   `frozen_clock` = `datetime(2026, 10, 26, 14, 30, tzinfo=timezone.utc)`.
5. **Threading, not asyncio.** Repository and session store use `threading.Lock`.
6. **Two-pass normaliser.** `intent_text` preserves number words; `digit_text`
   converts them.  `"like"` is NOT a filler word.
7. **Whole-word keyword matching** for intent detection (`\b` boundaries).
8. **Scoring formula:** best-hit weight + 0.15 per extra hit, capped at 1.0.
9. **Slot window:** today → today + 6 days (7 days).  Slots generated at runtime.
10. **Phone failures tracked per parcel across sessions** — parcel locked after limit.
11. **Rebook is atomic** (release old + book new in one lock).  Cancel releases slot.
12. **Empty text = silence**, never a 400 error.
13. **Separate counters** for silence and unknown intent.
14. **DELIVER_STATUS → CHOOSE_ACTION**, not END.
15. **TTS-friendly replies** — IDs read digit by digit, sentences ≤ 20 words.

---

## Completed steps

### Step 1 — Config, logging, app factory, health endpoint ✅

**Files created:**

| File | Purpose |
|------|---------|
| `app/core/__init__.py` | Core package marker |
| `app/core/config.py` | `Settings` class via pydantic-settings, `get_settings()` with `lru_cache` |
| `app/core/logging.py` | Stdlib JSON formatter, `setup_logging()`, `get_logger()` |
| `app/api/__init__.py` | API package marker |
| `app/api/routes/__init__.py` | Routes package marker |
| `app/api/routes/health.py` | `GET /health` → `{"status":"ok","version":"..."}` |
| `app/main.py` | `create_app()` factory, CORS from `CORS_ORIGINS`, lifespan hook |
| `tests/conftest.py` | `client` fixture (TestClient), `frozen_clock` fixture |
| `tests/test_health.py` | 8 tests: health response, CORS headers, app wiring |
| `tests/test_no_llm.py` | 15 parametrized tests: one per banned AI SDK substring |

**Files modified:**

| File | Change |
|------|--------|
| `backend/requirements.txt` | Added `pydantic-settings==2.9.1`, `pytest-cov==6.2.1`, `python-dotenv==1.1.0` |
| `.env.example` | All config vars documented |
| `README.md` | Setup, run, and test instructions |

**Test results:**
```
23 passed, 1 warning in 0.17s
```

---

## Next step

### Step 2 — Fake data layer

Build the data layer per PLAN.md §2.3–2.5 and §6:

1. Write `backend/data/parcels.json` (20+ parcels across 6 statuses).
2. Write `backend/data/slots.json` (capacity template, pre-booked offsets).
3. Write `backend/data/pickup_points.json` (5 pickup points).
4. Create `app/models/parcel.py` (Parcel, DeliverySlot, PickupPoint, ParcelStatus).
5. Create `app/data/loader.py` (load JSON, generate slot grid from clock).
6. Create `app/data/interfaces.py` (IParcelRepository, ISessionStore ABCs).
7. Create `app/data/repository.py` (InMemoryParcelRepository with threading.Lock,
   phone_failures tracking, InMemorySessionStore with per-session lock).
8. Write `tests/test_repository.py`.
9. Update `DESIGN.md`.

---

## Decisions that differ from PLAN.md

*None so far — Step 1 followed the plan exactly.*

---

## How to run tests

```bash
cd d:\Projects\test\savvpro-test-voice-agent\backend
d:\Projects\test\savvpro-test-voice-agent\backend\.venv\Scripts\python.exe -m pytest tests/ -v
```

With coverage:
```bash
d:\Projects\test\savvpro-test-voice-agent\backend\.venv\Scripts\python.exe -m pytest tests/ --cov=app --cov-report=term-missing
```

**Latest result (Step 1):**
```
23 passed, 1 warning in 0.17s
```

---

## Known issues

- `StarletteDeprecationWarning` about `httpx` vs `httpx2` in test client.
  Cosmetic; does not affect functionality.  Will resolve when starlette
  updates or when we bump the httpx dependency.

---

## File inventory (so far)

```
backend/
├── app/
│   ├── __init__.py              (pre-existing, empty)
│   ├── main.py                  ← Step 1
│   ├── api/
│   │   ├── __init__.py          ← Step 1
│   │   └── routes/
│   │       ├── __init__.py      ← Step 1
│   │       └── health.py        ← Step 1
│   └── core/
│       ├── __init__.py          ← Step 1
│       ├── config.py            ← Step 1
│       └── logging.py           ← Step 1
├── tests/
│   ├── __init__.py              (pre-existing, empty)
│   ├── conftest.py              ← Step 1
│   ├── test_health.py           ← Step 1
│   └── test_no_llm.py           ← Step 1
└── requirements.txt             ← Step 1 (modified)
```
