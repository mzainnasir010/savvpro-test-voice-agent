"""State machine — the brain of REDELIVER.

All transitions are explicit ``if/elif`` chains; no dynamic dispatch.
No external AI, no LLM calls.  The ``clock`` is injected, never read
from the system.

Flow:
    normalise input → run slot filler → run intent detector (with state
    context) → apply cross-cutting rules → apply state-specific transitions
    → call service functions → build and return trace.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.brain.constants import (
    MESSAGES,
    PARCEL_STATUS_RULES,
    STT_CONFIDENCE_THRESHOLD,
)
from app.brain.intent_detector import detect_intent
from app.brain.normalizer import normalize
from app.brain.slot_filler import (
    fill_from_turn,
    reset_action_slots,
    reset_date_slots,
)
from app.data.interfaces import IParcelRepository
from app.models.session import DecisionTrace, DialogueState, Session, Turn
from app.services.booking import (
    book_slot,
    find_nearest_available,
    get_available_slots,
    rebook_slot,
)
from app.services.cancellation import cancel_parcel
from app.services.pickup import list_pickup_points
from app.services.verification import verify_phone, verify_tracking_id


# ── Helpers ───────────────────────────────────────────────────────────


def _tracking_id_spoken(tracking_id: str) -> str:
    """Format a tracking ID for TTS: R. D. 1. 2. 3. 4. 5. 6. 7. 8."""
    return ". ".join(tracking_id)


def _format_date(d) -> str:
    """Format a date for TTS."""
    return d.strftime("%A %B %d").replace(" 0", " ")


# ── TurnResult ────────────────────────────────────────────────────────


class TurnResult:
    """Output of :meth:`StateMachine.process`."""

    __slots__ = ("reply", "trace", "ended")

    def __init__(
        self,
        reply: str,
        trace: DecisionTrace,
        ended: bool = False,
    ) -> None:
        self.reply = reply
        self.trace = trace
        self.ended = ended


# ── State Machine ─────────────────────────────────────────────────────


class StateMachine:
    """Deterministic dialogue state machine."""

    def __init__(
        self,
        repo: IParcelRepository,
        max_tracking_attempts: int = 3,
        max_phone_attempts: int = 3,
        max_silence_turns: int = 3,
        max_unknown_turns: int = 3,
    ) -> None:
        self._repo = repo
        self._max_tracking = max_tracking_attempts
        self._max_phone = max_phone_attempts
        self._max_silence = max_silence_turns
        self._max_unknown = max_unknown_turns

    # ── Public entry point ────────────────────────────────────────────

    def process(
        self,
        session: Session,
        turn_text: str,
        clock: datetime,
        silence: bool = False,
        stt_confidence: float = 1.0,
    ) -> TurnResult:
        """Process one caller turn and return the assistant reply.

        Args:
            session: The caller's session (mutated in place).
            turn_text: Raw transcribed text from the caller.
            clock: Injected datetime — never reads system clock.
            silence: True if no speech was detected.
            stt_confidence: STT confidence score (0.0–1.0).

        Returns:
            A ``TurnResult`` with reply text, decision trace, and ended flag.
        """
        trace = DecisionTrace(state_before=session.state.value)

        # Record user turn.
        session.history.append(Turn(role="user", text=turn_text))

        # ── Cross-cutting: END state ──────────────────────────────────
        if session.state == DialogueState.END:
            reply = MESSAGES["session_ended"]
            trace.state_after = DialogueState.END.value
            return self._finish(session, reply, trace, ended=True)

        # ── Cross-cutting: silence ────────────────────────────────────
        if silence or (not turn_text.strip()):
            session.silence_count += 1
            if session.silence_count >= self._max_silence:
                reply = MESSAGES["silence_3"]
                session.state = DialogueState.END
                session.ended = True
                trace.state_after = DialogueState.END.value
                return self._finish(session, reply, trace, ended=True)
            elif session.silence_count == 2:
                reply = MESSAGES["silence_2"]
            else:
                reply = MESSAGES["silence_1"]
            trace.state_after = session.state.value
            return self._finish(session, reply, trace)

        # Reset silence counter on any non-empty input.
        session.silence_count = 0

        # ── Cross-cutting: low STT confidence ─────────────────────────
        if stt_confidence < STT_CONFIDENCE_THRESHOLD:
            reply = MESSAGES["stt_low_confidence"]
            trace.state_after = session.state.value
            return self._finish(session, reply, trace)

        # ── Normalise ─────────────────────────────────────────────────
        norm = normalize(turn_text)

        # ── Slot filling ──────────────────────────────────────────────
        extracted = fill_from_turn(
            session.slots, norm, clock, session.state.value
        )
        trace.slots_extracted = extracted

        # ── Intent detection ──────────────────────────────────────────
        intent_result = detect_intent(norm.intent_text, session.state.value)
        trace.intent = intent_result.intent
        trace.intent_confidence = intent_result.confidence
        trace.runner_up = intent_result.runner_up
        trace.runner_up_confidence = intent_result.runner_up_confidence
        intent = intent_result.intent

        # ── Cross-cutting: repeat ─────────────────────────────────────
        if intent == "repeat":
            reply = session.last_assistant_reply or MESSAGES["repeat_no_previous"]
            trace.state_after = session.state.value
            return self._finish(session, reply, trace)

        # ── Cross-cutting: human_agent ────────────────────────────────
        if intent == "human_agent":
            reply = MESSAGES["human_handoff"]
            session.state = DialogueState.END
            session.ended = True
            trace.state_after = DialogueState.END.value
            return self._finish(session, reply, trace, ended=True)

        # ── Cross-cutting: goodbye ────────────────────────────────────
        if intent == "goodbye":
            reply = MESSAGES["goodbye"]
            session.state = DialogueState.END
            session.ended = True
            trace.state_after = DialogueState.END.value
            return self._finish(session, reply, trace, ended=True)

        # ── State-specific transitions ────────────────────────────────
        reply = self._dispatch(session, intent, clock, trace)

        # ── Cross-cutting: unknown escalation ─────────────────────────
        # (already handled inside _dispatch for relevant states)

        trace.state_after = session.state.value
        return self._finish(
            session, reply, trace, ended=session.state == DialogueState.END
        )

    # ── Dispatch ──────────────────────────────────────────────────────

    def _dispatch(
        self,
        session: Session,
        intent: str,
        clock: datetime,
        trace: DecisionTrace,
    ) -> str:
        state = session.state

        if state == DialogueState.COLLECT_TRACKING_ID:
            return self._on_collect_tracking_id(session, intent, trace)

        elif state == DialogueState.CONFIRM_TRACKING_ID:
            return self._on_confirm_tracking_id(session, intent, trace)

        elif state == DialogueState.VERIFY_PHONE:
            return self._on_verify_phone(session, intent, trace)

        elif state == DialogueState.CHOOSE_ACTION:
            return self._on_choose_action(session, intent, clock, trace)

        elif state == DialogueState.COLLECT_DATE:
            return self._on_collect_date(session, intent, clock, trace)

        elif state == DialogueState.COLLECT_PERIOD:
            return self._on_collect_period(session, intent, clock, trace)

        elif state == DialogueState.CONFIRM_SLOT:
            return self._on_confirm_slot(session, intent, clock, trace)

        elif state == DialogueState.COLLECT_PICKUP_POINT:
            return self._on_collect_pickup_point(session, intent, trace)

        elif state == DialogueState.CONFIRM_PICKUP:
            return self._on_confirm_pickup(session, intent, trace)

        elif state == DialogueState.CONFIRM_CANCEL:
            return self._on_confirm_cancel(session, intent, trace)

        elif state == DialogueState.DELIVER_STATUS:
            return self._on_deliver_status(session, trace)

        # Fallback (should not reach here).
        return self._handle_unknown(session, trace)

    # ── COLLECT_TRACKING_ID ───────────────────────────────────────────

    def _on_collect_tracking_id(
        self, session: Session, intent: str, trace: DecisionTrace
    ) -> str:
        session.tracking_attempts += 1
        slots = session.slots

        # 2+ tracking IDs.
        if slots.ambiguous_ids:
            ids_spoken = [_tracking_id_spoken(i) for i in slots.ambiguous_ids]
            return MESSAGES["tracking_multiple"].format(
                id_a=ids_spoken[0], id_b=ids_spoken[1]
            )

        # 1 tracking ID extracted.
        if slots.tracking_id:
            parcel = verify_tracking_id(self._repo, slots.tracking_id)
            if parcel:
                session.state = DialogueState.CONFIRM_TRACKING_ID
                spoken = _tracking_id_spoken(slots.tracking_id)
                return MESSAGES["tracking_confirm"].format(
                    tracking_id_spoken=spoken
                )
            else:
                slots.tracking_id = None
                return MESSAGES["tracking_not_found"]

        # No tracking ID extracted.
        if session.tracking_attempts >= self._max_tracking:
            session.state = DialogueState.END
            session.ended = True
            return MESSAGES["tracking_max_attempts"]

        return MESSAGES["ask_tracking_id"]

    # ── CONFIRM_TRACKING_ID ───────────────────────────────────────────

    def _on_confirm_tracking_id(
        self, session: Session, intent: str, trace: DecisionTrace
    ) -> str:
        slots = session.slots

        # Correction: new tracking ID in this turn.
        if "tracking_id" in trace.slots_extracted:
            parcel = verify_tracking_id(self._repo, slots.tracking_id)
            if parcel:
                spoken = _tracking_id_spoken(slots.tracking_id)
                return MESSAGES["tracking_confirm"].format(
                    tracking_id_spoken=spoken
                )
            else:
                slots.tracking_id = None
                session.state = DialogueState.COLLECT_TRACKING_ID
                return MESSAGES["tracking_not_found"]

        if intent == "affirm":
            session.state = DialogueState.VERIFY_PHONE
            return MESSAGES["ask_phone"]

        if intent == "deny":
            slots.tracking_id = None
            session.state = DialogueState.COLLECT_TRACKING_ID
            return MESSAGES["ask_tracking_id"]

        # Anything else — re-ask.
        spoken = _tracking_id_spoken(slots.tracking_id) if slots.tracking_id else ""
        return MESSAGES["tracking_confirm"].format(tracking_id_spoken=spoken)

    # ── VERIFY_PHONE ──────────────────────────────────────────────────

    def _on_verify_phone(
        self, session: Session, intent: str, trace: DecisionTrace
    ) -> str:
        slots = session.slots
        parcel = verify_tracking_id(self._repo, slots.tracking_id)

        if not parcel:
            session.state = DialogueState.COLLECT_TRACKING_ID
            return MESSAGES["tracking_not_found"]

        # Already locked.
        if self._repo.is_parcel_locked(parcel.tracking_id):
            session.state = DialogueState.END
            session.ended = True
            return MESSAGES["phone_locked"]

        if slots.phone_last4:
            if verify_phone(self._repo, parcel, slots.phone_last4):
                slots.verified = True
                session.state = DialogueState.CHOOSE_ACTION
                session.phone_attempts = 0
                return MESSAGES["verified_menu"]
            else:
                session.phone_attempts += 1
                slots.phone_last4 = None
                if session.phone_attempts >= self._max_phone:
                    session.state = DialogueState.END
                    session.ended = True
                    return MESSAGES["phone_locked"]
                return MESSAGES["phone_wrong"]

        # No phone digits extracted.
        return MESSAGES["ask_phone"]

    # ── CHOOSE_ACTION ─────────────────────────────────────────────────

    def _on_choose_action(
        self,
        session: Session,
        intent: str,
        clock: datetime,
        trace: DecisionTrace,
    ) -> str:
        slots = session.slots
        parcel = verify_tracking_id(self._repo, slots.tracking_id)
        if not parcel:
            session.state = DialogueState.COLLECT_TRACKING_ID
            return MESSAGES["tracking_not_found"]

        allowed = PARCEL_STATUS_RULES.get(parcel.status.value, set())

        if intent == "reschedule":
            if "reschedule" in allowed:
                slots.action_intent = "reschedule"
                session.state = DialogueState.COLLECT_DATE
                # Reset unknown counter on valid action.
                session.unknown_count = 0
                return MESSAGES["ask_date"]
            else:
                return MESSAGES["status_blocked"].format(
                    status=parcel.status.value.replace("_", " ")
                )

        if intent == "pickup_point":
            if "pickup_point" in allowed:
                slots.action_intent = "pickup_point"
                session.state = DialogueState.COLLECT_PICKUP_POINT
                session.unknown_count = 0
                points = list_pickup_points(self._repo)
                points_list = "; ".join(
                    f"{i+1}. {p.name} at {p.address}"
                    for i, p in enumerate(points)
                )
                return MESSAGES["list_pickup_points"].format(
                    points_list=points_list
                )
            else:
                return MESSAGES["status_blocked"].format(
                    status=parcel.status.value.replace("_", " ")
                )

        if intent == "cancel":
            if "cancel" in allowed:
                slots.action_intent = "cancel"
                session.state = DialogueState.CONFIRM_CANCEL
                session.unknown_count = 0
                return MESSAGES["confirm_cancel"]
            else:
                return MESSAGES["status_blocked"].format(
                    status=parcel.status.value.replace("_", " ")
                )

        if intent == "status":
            session.state = DialogueState.DELIVER_STATUS
            session.unknown_count = 0
            return self._on_deliver_status(session, trace)

        if intent == "change_of_mind":
            reset_action_slots(slots)
            session.unknown_count = 0
            return MESSAGES["change_of_mind_menu"]

        # Unknown or affirm/deny in wrong context.
        return self._handle_unknown(session, trace)

    # ── COLLECT_DATE ──────────────────────────────────────────────────

    def _on_collect_date(
        self,
        session: Session,
        intent: str,
        clock: datetime,
        trace: DecisionTrace,
    ) -> str:
        slots = session.slots

        # Change of mind → back to menu.
        if intent == "change_of_mind":
            reset_action_slots(slots)
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["change_of_mind_menu"]

        # Date rejection.
        if "date_rejection" in trace.slots_extracted:
            reason = trace.slots_extracted["date_rejection"]
            if reason == "past":
                return MESSAGES["date_past"]
            elif reason == "out_of_range":
                return MESSAGES["date_out_of_range"]
            elif reason == "cutoff":
                return MESSAGES["date_cutoff"]

        # Period cutoff.
        if "period_cutoff" in trace.slots_extracted:
            return MESSAGES["date_cutoff"]

        # Date extracted.
        if slots.intended_date:
            # Check if period also extracted.
            if slots.intended_period:
                avail = get_available_slots(
                    self._repo, slots.intended_date, clock,
                    period=slots.intended_period,
                )
                if avail:
                    slots.confirmed_slot_id = avail[0].slot_id
                    session.state = DialogueState.CONFIRM_SLOT
                    return MESSAGES["confirm_slot"].format(
                        period=slots.intended_period,
                        date=_format_date(slots.intended_date),
                    )
                else:
                    # No slot for that period — offer alternative.
                    alt = find_nearest_available(self._repo, clock)
                    if alt:
                        return MESSAGES["slot_full"].format(
                            period=slots.intended_period,
                            date=_format_date(slots.intended_date),
                            alt_period=alt.period.value if hasattr(alt.period, 'value') else alt.period,
                            alt_date=_format_date(alt.date),
                        )
                    return MESSAGES["date_out_of_range"]
            else:
                # Date but no period — check any slots on that day.
                avail = get_available_slots(
                    self._repo, slots.intended_date, clock,
                )
                if avail:
                    session.state = DialogueState.COLLECT_PERIOD
                    return MESSAGES["ask_period"]
                else:
                    # No slots at all on that day.
                    alt = find_nearest_available(
                        self._repo, clock,
                        exclude_date=slots.intended_date,
                    )
                    reset_date_slots(slots)
                    if alt:
                        return MESSAGES["no_slots_on_day"].format(
                            date=_format_date(slots.intended_date or clock.date()),
                            alt_period=alt.period.value if hasattr(alt.period, 'value') else alt.period,
                            alt_date=_format_date(alt.date),
                        )
                    return MESSAGES["date_out_of_range"]

        # No date extracted.
        return MESSAGES["ask_date"]

    # ── COLLECT_PERIOD ────────────────────────────────────────────────

    def _on_collect_period(
        self,
        session: Session,
        intent: str,
        clock: datetime,
        trace: DecisionTrace,
    ) -> str:
        slots = session.slots

        if intent == "change_of_mind":
            reset_action_slots(slots)
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["change_of_mind_menu"]

        # New date extracted → reset period and go to COLLECT_DATE.
        if "intended_date" in trace.slots_extracted:
            slots.intended_period = None
            slots.confirmed_slot_id = None
            session.state = DialogueState.COLLECT_DATE
            return self._on_collect_date(session, intent, clock, trace)

        if slots.intended_period and slots.intended_date:
            avail = get_available_slots(
                self._repo, slots.intended_date, clock,
                period=slots.intended_period,
            )
            if avail:
                slots.confirmed_slot_id = avail[0].slot_id
                session.state = DialogueState.CONFIRM_SLOT
                return MESSAGES["confirm_slot"].format(
                    period=slots.intended_period,
                    date=_format_date(slots.intended_date),
                )
            else:
                # Period not available — list what is.
                avail_any = get_available_slots(
                    self._repo, slots.intended_date, clock,
                )
                if avail_any:
                    period_list = ", ".join(
                        s.period.value if hasattr(s.period, 'value') else s.period
                        for s in avail_any
                    )
                    slots.intended_period = None
                    return (
                        f"No {slots.intended_period or 'that'} slot that day. "
                        f"Available: {period_list}. Which do you prefer?"
                    )
                # No slots at all on that day.
                alt = find_nearest_available(self._repo, clock)
                reset_date_slots(slots)
                session.state = DialogueState.COLLECT_DATE
                if alt:
                    return MESSAGES["no_slots_on_day"].format(
                        date=_format_date(slots.intended_date or clock.date()),
                        alt_period=alt.period.value if hasattr(alt.period, 'value') else alt.period,
                        alt_date=_format_date(alt.date),
                    )
                return MESSAGES["date_out_of_range"]

        return MESSAGES["ask_period"]

    # ── CONFIRM_SLOT ──────────────────────────────────────────────────

    def _on_confirm_slot(
        self,
        session: Session,
        intent: str,
        clock: datetime,
        trace: DecisionTrace,
    ) -> str:
        slots = session.slots

        if intent == "affirm" and slots.confirmed_slot_id:
            parcel = verify_tracking_id(self._repo, slots.tracking_id)
            if parcel and parcel.current_slot_id:
                # Rebook.
                success = rebook_slot(
                    self._repo,
                    parcel.current_slot_id,
                    slots.confirmed_slot_id,
                    slots.tracking_id,
                )
            else:
                success = book_slot(
                    self._repo, slots.confirmed_slot_id, slots.tracking_id,
                )
            if success:
                session.state = DialogueState.END
                session.ended = True
                msg_key = "rebooked" if (parcel and parcel.current_slot_id) else "booked"
                return MESSAGES[msg_key].format(
                    date=_format_date(slots.intended_date),
                    period=slots.intended_period,
                )
            else:
                # Slot became full between confirm and book.
                alt = find_nearest_available(self._repo, clock)
                if alt:
                    slots.confirmed_slot_id = alt.slot_id
                    slots.intended_date = alt.date
                    slots.intended_period = alt.period.value if hasattr(alt.period, 'value') else alt.period
                    return MESSAGES["slot_full"].format(
                        period=slots.intended_period,
                        date=_format_date(slots.intended_date),
                        alt_period=alt.period.value if hasattr(alt.period, 'value') else alt.period,
                        alt_date=_format_date(alt.date),
                    )
                return MESSAGES["date_out_of_range"]

        if intent == "deny":
            reset_date_slots(slots)
            session.state = DialogueState.COLLECT_DATE
            return MESSAGES["ask_date"]

        if intent == "change_of_mind":
            reset_action_slots(slots)
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["change_of_mind_menu"]

        # New date or period extracted → re-collect.
        if "intended_date" in trace.slots_extracted or "intended_period" in trace.slots_extracted:
            reset_date_slots(slots)
            session.state = DialogueState.COLLECT_DATE
            return self._on_collect_date(session, intent, clock, trace)

        # Re-ask.
        if slots.intended_date and slots.intended_period:
            return MESSAGES["confirm_slot"].format(
                period=slots.intended_period,
                date=_format_date(slots.intended_date),
            )
        return MESSAGES["ask_date"]

    # ── COLLECT_PICKUP_POINT ──────────────────────────────────────────

    def _on_collect_pickup_point(
        self, session: Session, intent: str, trace: DecisionTrace
    ) -> str:
        slots = session.slots

        if intent == "change_of_mind":
            reset_action_slots(slots)
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["change_of_mind_menu"]

        points = list_pickup_points(self._repo)

        # Try to match by ordinal number (1, 2, 3...).
        digit_text = trace.slots_extracted.get("phone_last4", "")
        # Also check the raw intent text for a number.
        for i, p in enumerate(points):
            name_lower = p.name.lower()
            # Check if user said the point name.
            if name_lower in (session.history[-1].text.lower() if session.history else ""):
                slots.pickup_point_id = p.point_id
                session.state = DialogueState.CONFIRM_PICKUP
                return MESSAGES["confirm_pickup"].format(
                    name=p.name, address=p.address,
                )
            # Check if user said the ordinal number.
            user_text = session.history[-1].text.lower() if session.history else ""
            ordinal = str(i + 1)
            if ordinal in user_text:
                slots.pickup_point_id = p.point_id
                session.state = DialogueState.CONFIRM_PICKUP
                return MESSAGES["confirm_pickup"].format(
                    name=p.name, address=p.address,
                )

        # No valid selection.
        points_list = "; ".join(
            f"{i+1}. {p.name} at {p.address}" for i, p in enumerate(points)
        )
        return MESSAGES["list_pickup_points"].format(points_list=points_list)

    # ── CONFIRM_PICKUP ────────────────────────────────────────────────

    def _on_confirm_pickup(
        self, session: Session, intent: str, trace: DecisionTrace
    ) -> str:
        slots = session.slots

        if intent == "affirm":
            point = self._repo.get_pickup_point(slots.pickup_point_id)
            session.state = DialogueState.END
            session.ended = True
            name = point.name if point else "the pickup point"
            return MESSAGES["pickup_done"].format(name=name)

        if intent == "deny":
            slots.pickup_point_id = None
            session.state = DialogueState.COLLECT_PICKUP_POINT
            points = list_pickup_points(self._repo)
            points_list = "; ".join(
                f"{i+1}. {p.name} at {p.address}" for i, p in enumerate(points)
            )
            return MESSAGES["list_pickup_points"].format(points_list=points_list)

        if intent == "change_of_mind":
            reset_action_slots(slots)
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["change_of_mind_menu"]

        # Re-ask.
        point = self._repo.get_pickup_point(slots.pickup_point_id)
        if point:
            return MESSAGES["confirm_pickup"].format(
                name=point.name, address=point.address,
            )
        return MESSAGES["ask_tracking_id"]

    # ── CONFIRM_CANCEL ────────────────────────────────────────────────

    def _on_confirm_cancel(
        self, session: Session, intent: str, trace: DecisionTrace
    ) -> str:
        if intent == "affirm":
            cancel_parcel(self._repo, session.slots.tracking_id)
            session.state = DialogueState.END
            session.ended = True
            return MESSAGES["cancelled"]

        if intent == "deny":
            session.slots.cancel_confirmed = False
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["cancel_denied"]

        if intent == "change_of_mind":
            reset_action_slots(session.slots)
            session.state = DialogueState.CHOOSE_ACTION
            return MESSAGES["change_of_mind_menu"]

        # Re-ask.
        return MESSAGES["confirm_cancel"]

    # ── DELIVER_STATUS ────────────────────────────────────────────────

    def _on_deliver_status(
        self, session: Session, trace: DecisionTrace
    ) -> str:
        parcel = verify_tracking_id(self._repo, session.slots.tracking_id)
        status_text = (
            parcel.status.value.replace("_", " ") if parcel else "unknown"
        )
        session.state = DialogueState.CHOOSE_ACTION
        return (
            f"Your parcel is currently {status_text}. "
            + MESSAGES["anything_else"]
        )

    # ── Unknown handling ──────────────────────────────────────────────

    def _handle_unknown(
        self, session: Session, trace: DecisionTrace
    ) -> str:
        session.unknown_count += 1
        if session.unknown_count >= self._max_unknown:
            session.state = DialogueState.END
            session.ended = True
            return MESSAGES["unknown_3"]
        elif session.unknown_count == 2:
            return MESSAGES["unknown_2"]
        return MESSAGES["unknown_1"]

    # ── Finish helper ─────────────────────────────────────────────────

    def _finish(
        self,
        session: Session,
        reply: str,
        trace: DecisionTrace,
        ended: bool = False,
    ) -> TurnResult:
        """Record the assistant reply and return the result."""
        session.last_assistant_reply = reply
        session.history.append(Turn(role="assistant", text=reply, trace=trace))
        if ended:
            session.ended = True
        return TurnResult(reply=reply, trace=trace, ended=ended)
