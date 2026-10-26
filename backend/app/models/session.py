"""Session model — minimal definition for Step 2.

This module will be expanded in Step 7 with DialogueState, SlotMap, Turn,
and DecisionTrace.  For now it holds just enough for the session store to
operate.
"""

from __future__ import annotations

import threading
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Session(BaseModel):
    """A caller's conversation session.

    The ``lock`` field serialises concurrent turns for the same session.
    It is excluded from JSON serialisation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    created_at: datetime
    ended: bool = False

    # Per-session threading lock — excluded from serialisation.
    lock: threading.Lock = Field(
        default_factory=threading.Lock,
        exclude=True,
        repr=False,
    )
