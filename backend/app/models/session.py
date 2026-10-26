"""Session model — expanded for the state machine (Step 7).

Contains:
- ``DialogueState`` enum — the 13 dialogue states.
- ``SlotMap`` — all collected caller information.
- ``Turn`` — one turn of conversation history.
- ``DecisionTrace`` — debugging breadcrumbs for each turn.
- ``Session`` — the caller's conversation session.
"""

from __future__ import annotations

import enum
import threading
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DialogueState(str, enum.Enum):
    """The 13 dialogue states."""

    GREETING = "GREETING"
    COLLECT_TRACKING_ID = "COLLECT_TRACKING_ID"
    CONFIRM_TRACKING_ID = "CONFIRM_TRACKING_ID"
    VERIFY_PHONE = "VERIFY_PHONE"
    CHOOSE_ACTION = "CHOOSE_ACTION"
    COLLECT_DATE = "COLLECT_DATE"
    COLLECT_PERIOD = "COLLECT_PERIOD"
    CONFIRM_SLOT = "CONFIRM_SLOT"
    COLLECT_PICKUP_POINT = "COLLECT_PICKUP_POINT"
    CONFIRM_PICKUP = "CONFIRM_PICKUP"
    CONFIRM_CANCEL = "CONFIRM_CANCEL"
    DELIVER_STATUS = "DELIVER_STATUS"
    END = "END"


class SlotMap(BaseModel):
    """All collected caller information.

    Slots are mutable; the slot filler and state machine update them.
    """

    tracking_id: Optional[str] = None
    ambiguous_ids: list[str] = Field(default_factory=list)
    phone_last4: Optional[str] = None
    intended_date: Optional[date] = None
    intended_period: Optional[str] = None
    confirmed_slot_id: Optional[str] = None
    pickup_point_id: Optional[str] = None
    action_intent: Optional[str] = None
    cancel_confirmed: bool = False

    # Verification flag.
    verified: bool = False


class DecisionTrace(BaseModel):
    """Debugging breadcrumbs for a single turn."""

    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    runner_up: Optional[str] = None
    runner_up_confidence: Optional[float] = None
    slots_extracted: dict[str, object] = Field(default_factory=dict)
    state_before: Optional[str] = None
    state_after: Optional[str] = None
    rejection_reason: Optional[str] = None


class Turn(BaseModel):
    """One turn of conversation history."""

    role: str  # "user" or "assistant"
    text: str
    trace: Optional[DecisionTrace] = None


class Session(BaseModel):
    """A caller's conversation session.

    The ``lock`` field serialises concurrent turns for the same session.
    It is excluded from JSON serialisation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    created_at: datetime
    ended: bool = False
    state: DialogueState = DialogueState.GREETING
    slots: SlotMap = Field(default_factory=SlotMap)
    history: list[Turn] = Field(default_factory=list)
    last_assistant_reply: str = ""

    # Counters.
    silence_count: int = 0
    unknown_count: int = 0
    tracking_attempts: int = 0
    phone_attempts: int = 0

    # Per-session threading lock — excluded from serialisation.
    lock: threading.Lock = Field(
        default_factory=threading.Lock,
        exclude=True,
        repr=False,
    )
