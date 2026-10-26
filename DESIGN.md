# REDELIVER — Design Document

## Use Case

**REDELIVER** is a voice assistant for missed-delivery rescheduling. When a
parcel delivery fails (nobody home, wrong address, etc.), the recipient can
call REDELIVER and:

1. **Reschedule** the delivery to a new date and time window.
2. **Redirect** the parcel to a nearby pickup point.
3. **Cancel** the delivery entirely.
4. **Check status** of the parcel.

The assistant handles the entire conversation — from caller identification
through to confirmation — without any human operator.

## The Brain: How Decisions Are Made

> **No LLM is used anywhere in the decision logic.** All intent detection,
> slot filling, and state transitions are plain Python code.

### Architecture Overview

```
Caller speaks
    → STT transcription
    → Two-pass normalizer (intent_text + digit_text)
    → Slot filler (extracts tracking ID, phone, date, period)
    → Intent detector (weighted keyword scoring, state-aware priority)
    → State machine (explicit if/elif transitions)
    → Service layer (verification, booking, pickup, cancellation)
    → TTS-friendly reply
    → Caller hears response
```

### Text Normalizer (Two-Pass)

The normalizer produces two outputs from each raw transcription:

- **`intent_text`**: Number words preserved ("oh no" stays as "oh no", "one
  moment" stays as "one moment"). Used for intent detection where number
  words carry meaning.
- **`digit_text`**: Number words converted to digits ("five" → "5",
  "double oh" → "00", "triple nine" → "999"). Used by the tracking ID
  extractor and date parser.

Both passes share common preprocessing:
1. Lowercase and strip whitespace.
2. Remove non-printable characters (injection protection).
3. Truncate to 2000 characters max.
4. Strip speech fillers ("uh", "um", "er", "you know", etc.) — but
   **"like" is NOT stripped** to preserve "I'd like to…".
5. Collapse whitespace.

### Intent Detection

Weighted keyword + regex scoring with no external AI:

```
score = best_hit_weight + 0.15 × (extra_hits)  [capped at 1.0]
```

State-aware priority ensures `affirm`/`deny` win in confirmation states,
and disambiguation rules handle ambiguous phrases ("no wait" →
`change_of_mind`, "cancel that" → `deny`).

### State Machine

12 dialogue states with explicit transitions. Cross-cutting handlers for
silence, repeat requests, human agent handoff, and goodbye are checked
before state-specific logic.

### Data Layer

- **Parcels**: 21 fake parcels across 6 statuses (in_transit,
  out_for_delivery, failed_attempt, delivered, cancelled,
  returned_to_sender).
- **Delivery slots**: Generated at runtime from an injected clock (7-day
  window, 3 periods per day). Pre-booked entries create deterministic
  edge cases (fully booked day, nearly-full slots).
- **Pickup points**: 5 locations with varied opening schedules (weekday-only,
  7-day, closed Mondays, etc.).

All data is fake. No real people's details.

### Thread Safety

- `InMemoryParcelRepository` uses `threading.Lock` for all mutations.
- Booking and releasing are atomic; rebooking (release old + book new)
  happens in a single lock acquisition.
- `InMemorySessionStore` has a store-level lock plus per-session locks
  for turn serialisation.
