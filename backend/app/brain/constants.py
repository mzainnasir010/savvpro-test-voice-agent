"""Brain-layer constants — phrases, thresholds, and message templates.

Step 3 populates the normalizer-related constants (FILLER_WORDS,
NUMBER_WORD_MAP, DOUBLE_TRIPLE_PATTERN).  Intent keyword tables will be
fleshed out in Step 6.
"""

from __future__ import annotations

import re

# ── Filler words ──────────────────────────────────────────────────────
#
# Speech disfluencies stripped during normalisation.
# **"like" is NOT included** — it must survive to keep "I'd like to…".

FILLER_WORDS: frozenset[str] = frozenset(
    {
        "uh",
        "um",
        "uhm",
        "umm",
        "erm",
        "er",
        "ah",
        "hmm",
        "hm",
        "you know",
        "sort of",
        "kind of",
        "i mean",
        "basically",
        "literally",
        "right so",
    }
)

# ── Number-word → digit map ──────────────────────────────────────────
#
# Ordered **longest-first** so that multi-word entries are replaced before
# single-word ones (e.g. "twenty one" before "one").

NUMBER_WORD_MAP: list[tuple[str, str]] = [
    # Teens & compounds (longest first)
    ("twenty one", "21"),
    ("twenty two", "22"),
    ("twenty three", "23"),
    ("twenty four", "24"),
    ("twenty five", "25"),
    ("twenty six", "26"),
    ("twenty seven", "27"),
    ("twenty eight", "28"),
    ("twenty nine", "29"),
    ("thirty one", "31"),
    ("thirty", "30"),
    ("twenty", "20"),
    ("nineteen", "19"),
    ("eighteen", "18"),
    ("seventeen", "17"),
    ("sixteen", "16"),
    ("fifteen", "15"),
    ("fourteen", "14"),
    ("thirteen", "13"),
    ("twelve", "12"),
    ("eleven", "11"),
    ("ten", "10"),
    # Single digits
    ("nine", "9"),
    ("eight", "8"),
    ("seven", "7"),
    ("six", "6"),
    ("five", "5"),
    ("four", "4"),
    ("three", "3"),
    ("two", "2"),
    ("one", "1"),
    ("zero", "0"),
]

# ── Double / triple patterns ─────────────────────────────────────────

DOUBLE_TRIPLE_PATTERN: re.Pattern[str] = re.compile(
    r"\b(double|triple)\s+(zero|oh|one|two|three|four|five|six|seven|eight|nine|\d)\b",
    re.IGNORECASE,
)

# Map used inside the double/triple replacer.
_WORD_TO_SINGLE_DIGIT: dict[str, str] = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

# ── "oh" → "0" context pattern ───────────────────────────────────────
#
# "oh" is converted to "0" only when it appears between digits, digit-words,
# or at the start/end of a digit sequence.  This avoids corrupting phrases
# like "oh no" in intent_text (which skips the digit pass entirely).

OH_DIGIT_CONTEXT: re.Pattern[str] = re.compile(
    r"(?<=[0-9])\s+oh\b|\boh\s+(?=[0-9])",
    re.IGNORECASE,
)

# ── Thresholds & limits ──────────────────────────────────────────────

MAX_INPUT_LENGTH: int = 2000

CONFIDENCE_THRESHOLD: float = 0.40
AMBIGUITY_MARGIN: float = 0.15
EXTRA_HIT_BONUS: float = 0.15
STT_CONFIDENCE_THRESHOLD: float = 0.50

# ── Parcel status rules ──────────────────────────────────────────────
#
# Maps a parcel status to the set of action intents the caller is allowed
# to perform.

PARCEL_STATUS_RULES: dict[str, set[str]] = {
    "failed_attempt": {"reschedule", "pickup_point", "cancel", "status"},
    "in_transit": {"status"},
    "out_for_delivery": {"status"},
    "delivered": {"status"},
    "cancelled": set(),
    "returned_to_sender": set(),
}

# ── RD phonetic prefixes ─────────────────────────────────────────────

RD_PHONETIC_PREFIXES: list[str] = [
    "rd",
    "r d",
    "are dee",
    "our d",
    "ardie",
]

# ── Messages (TTS-friendly) ──────────────────────────────────────────
#
# Placeholder keys use {slot} syntax; the state machine formats them.
# Sentences ≤ 20 words.

MESSAGES: dict[str, str] = {
    "greeting": (
        "Hello. Welcome to REDELIVER. I can help with a missed delivery. "
        "Please tell me your tracking ID. "
        "It starts with R. D. followed by 8 digits."
    ),
    "ask_tracking_id": (
        "Please say your tracking ID. "
        "It starts with R. D. followed by 8 digits."
    ),
    "tracking_not_found": (
        "I cannot find that parcel. Please try again."
    ),
    "tracking_confirm": (
        "I heard {tracking_id_spoken}. Is that correct?"
    ),
    "tracking_multiple": (
        "I heard two IDs. Which one did you mean? {id_a} or {id_b}?"
    ),
    "tracking_max_attempts": (
        "I was not able to find your tracking ID. "
        "Let me transfer you to a human agent. Goodbye."
    ),
    "ask_phone": (
        "Great. Please say the last 4 digits of your phone number."
    ),
    "phone_wrong": (
        "That did not match. Please try again."
    ),
    "phone_locked": (
        "For security I cannot continue. "
        "Please contact our support team. Goodbye."
    ),
    "verified_menu": (
        "Verified. What would you like to do? "
        "Reschedule, pick up from a point, cancel, or check status?"
    ),
    "status_blocked": (
        "Your parcel is currently {status}. "
        "That action is not available right now."
    ),
    "ask_date": (
        "What date works for you? I can book within the next 7 days."
    ),
    "ask_period": (
        "Which do you prefer? Morning, afternoon, or evening?"
    ),
    "confirm_slot": (
        "I have {period} on {date}. Shall I book that?"
    ),
    "slot_full": (
        "Sorry, {period} on {date} is fully booked. "
        "The nearest available is {alt_period} on {alt_date}. Want that?"
    ),
    "no_slots_on_day": (
        "No slots on {date}. The next available is {alt_period} on {alt_date}. "
        "Want that?"
    ),
    "date_past": (
        "That time has passed. Please choose a future date."
    ),
    "date_out_of_range": (
        "I can only book within the next 7 days."
    ),
    "date_cutoff": (
        "That time slot has already passed today. "
        "Please choose a later time or another day."
    ),
    "booked": (
        "Booked. Delivery on {date}, {period}. Goodbye."
    ),
    "rebooked": (
        "Rebooked. Your new delivery is {date}, {period}. Goodbye."
    ),
    "list_pickup_points": (
        "Here are the pickup points: {points_list}. "
        "Which one would you like?"
    ),
    "confirm_pickup": (
        "You chose {name} at {address}. Is that right?"
    ),
    "pickup_done": (
        "Noted. Please collect from {name}. Goodbye."
    ),
    "confirm_cancel": (
        "Are you sure you want to cancel your delivery? Say yes to confirm."
    ),
    "cancelled": (
        "Your delivery has been cancelled. Goodbye."
    ),
    "cancel_denied": (
        "OK, not cancelled. What else can I help with?"
    ),
    "anything_else": (
        "Is there anything else I can help you with?"
    ),
    "change_of_mind_menu": (
        "No problem. What would you like to do instead?"
    ),
    "silence_1": (
        "I did not hear anything. Are you still there?"
    ),
    "silence_2": (
        "I still cannot hear you. Please say something."
    ),
    "silence_3": (
        "I have not heard from you. I will end the call now. Goodbye."
    ),
    "unknown_1": (
        "I did not quite understand. Could you say that differently?"
    ),
    "unknown_2": (
        "I am still not sure what you need. "
        "You can say reschedule, pick up, cancel, or status."
    ),
    "unknown_3": (
        "I am having trouble understanding. "
        "Let me transfer you to a human agent. Goodbye."
    ),
    "stt_low_confidence": (
        "I did not quite catch that. Could you say that again?"
    ),
    "repeat_no_previous": (
        "I have not said anything yet. How can I help?"
    ),
    "human_handoff": (
        "Let me transfer you to a human agent now. Goodbye."
    ),
    "goodbye": (
        "Thank you for calling REDELIVER. Goodbye."
    ),
    "session_ended": (
        "This call has ended. Goodbye."
    ),
    "affirm_wrong_state": (
        "I am not sure what you are confirming. {re_ask}"
    ),
}
