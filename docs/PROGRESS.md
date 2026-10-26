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

### Step 2 — Fake data layer ✅

**Files created:**

| File | Purpose |
|------|---------|
| `backend/data/parcels.json` | 21 fake parcels across 6 statuses |
| `backend/data/slots.json` | Capacity template with pre-booked offsets (day 1 morning full, day 3 fully booked, day 5 evening nearly full) |
| `backend/data/pickup_points.json` | 5 pickup points: 2 weekday-only, 1 seven-day, 2 mixed |
| `app/models/parcel.py` | `Parcel`, `DeliverySlot`, `PickupPoint`, `ParcelStatus`, `Period`, `SlotTemplate`, `PreBookedEntry` |
| `app/models/session.py` | Minimal `Session` model (expanded in Step 7) |
| `app/data/interfaces.py` | `IParcelRepository`, `ISessionStore` ABCs |
| `app/data/loader.py` | `load_parcels`, `load_pickup_points`, `load_slots`, `generate_slots` (clock-injected) |
| `app/data/repository.py` | `InMemoryParcelRepository` (threading.Lock, atomic book/release/rebook/cancel), `InMemorySessionStore` |
| `tests/test_repository.py` | 62 tests: loader validation, slot generation, booking, concurrency, pickup filtering, cancel, phone failures, session store |

**Test results:**
```
85 passed, 2 warnings in 0.69s
```

---

### Step 3 — Text normalizer (two-pass) ✅

**Files created:**

| File | Purpose |
|------|---------|
| `app/brain/__init__.py` | Brain package marker |
| `app/brain/constants.py` | `FILLER_WORDS` (without "like"), `NUMBER_WORD_MAP` (longest-first), `DOUBLE_TRIPLE_PATTERN` (with "oh"), `OH_DIGIT_CONTEXT`, `_WORD_TO_SINGLE_DIGIT`, thresholds, `RD_PHONETIC_PREFIXES`, `MESSAGES`, `PARCEL_STATUS_RULES` |
| `app/brain/normalizer.py` | Two-pass normalizer: common preprocess → `intent_text`; additional digit pass → `digit_text`. Returns frozen `NormalizeResult` dataclass. |
| `tests/test_normalizer.py` | 64 tests: happy path, intent preservation ("oh no", "one moment"), digit conversion ("double five"→"55", "triple nine"→"999", "oh"→"0"), boundaries (empty, 2000, 2001), injection (HTML, SQL, Unicode), "like" preserved, 19 parametrized phrase pairs, return type |

**Design decisions:**
- `"oh"` added to `DOUBLE_TRIPLE_PATTERN` and `_WORD_TO_SINGLE_DIGIT` so "double oh" → "00".
- HTML angle brackets (printable ASCII) are preserved by the normalizer as harmless plain text — safety comes from the fact that output is never executed.
- `NormalizeResult` is a frozen dataclass for immutability.

**Test results:**
```
149 passed, 2 warnings in 0.49s
```

---

## Next step

### Step 4 — Tracking ID and phone extractor

Build per PLAN.md §2.11:

1. Create `app/brain/extractor.py` with:
   - `extract_tracking_ids(digit_text)` — phonetic RD prefix variants, 8 digits.
   - `extract_phone_last4(digit_text, exclude_digits)` — 4-digit extraction avoiding tracking ID overlap.
2. Write `tests/test_extractor.py` with 15+ tracking ID phrasings.

---

## Decisions that differ from PLAN.md

- **Step 3:** Added `"oh"` to `DOUBLE_TRIPLE_PATTERN` and `_WORD_TO_SINGLE_DIGIT`
  so that "double oh" → "00" (plan did not explicitly cover this compound).
- **Step 3:** HTML `<script>` tags are not stripped because `<` and `>` are
  printable ASCII.  The normalizer's safety guarantee is that output is
  plain text with no executable context, not that specific character
  sequences are removed.

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

**Latest result (Step 3):**
```
149 passed, 2 warnings in 0.49s
```

---

## Known issues

- `StarletteDeprecationWarning` about `httpx` vs `httpx2` in test client.
  Cosmetic; does not affect functionality.  Will resolve when starlette
  updates or when we bump the httpx dependency.
- `ArbitraryTypeWarning` from Pydantic about `threading.Lock` in `Session`.
  Cosmetic; lock works correctly.  Can wrap with `SkipValidation` later.

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
│   ├── brain/
│   │   ├── __init__.py          ← Step 3
│   │   ├── constants.py         ← Step 3
│   │   └── normalizer.py        ← Step 3
│   ├── core/
│   │   ├── __init__.py          ← Step 1
│   │   ├── config.py            ← Step 1
│   │   └── logging.py           ← Step 1
│   ├── data/
│   │   ├── __init__.py          ← Step 2
│   │   ├── interfaces.py        ← Step 2
│   │   ├── loader.py            ← Step 2
│   │   └── repository.py        ← Step 2
│   └── models/
│       ├── __init__.py          ← Step 2
│       ├── parcel.py            ← Step 2
│       └── session.py           ← Step 2
├── data/
│   ├── parcels.json             ← Step 2
│   ├── slots.json               ← Step 2
│   └── pickup_points.json       ← Step 2
├── tests/
│   ├── __init__.py              (pre-existing, empty)
│   ├── conftest.py              ← Step 1
│   ├── test_health.py           ← Step 1
│   ├── test_no_llm.py           ← Step 1
│   ├── test_normalizer.py       ← Step 3
│   └── test_repository.py       ← Step 2
└── requirements.txt             ← Step 1 (modified)
```
