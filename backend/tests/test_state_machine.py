"""Unit tests for the lead state machine."""

from __future__ import annotations

import pytest

from app.core.errors import InvalidStateTransitionError
from app.models.enums import LeadState
from app.services.state_machine import assert_can_transition, can_transition


def test_pending_may_move_to_reached_out():
    assert can_transition(LeadState.PENDING, LeadState.REACHED_OUT)
    assert_can_transition(LeadState.PENDING, LeadState.REACHED_OUT)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (LeadState.PENDING, LeadState.PENDING),
        (LeadState.REACHED_OUT, LeadState.REACHED_OUT),
        # Un-contacting someone is not a real event, so the reverse edge is
        # deliberately absent rather than merely undefined.
        (LeadState.REACHED_OUT, LeadState.PENDING),
    ],
)
def test_illegal_transitions_are_rejected(current: LeadState, target: LeadState):
    assert not can_transition(current, target)
    with pytest.raises(InvalidStateTransitionError):
        assert_can_transition(current, target)


def test_repeating_the_current_state_says_so():
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        assert_can_transition(LeadState.REACHED_OUT, LeadState.REACHED_OUT)

    assert "already in REACHED_OUT" in exc_info.value.message
    assert exc_info.value.status_code == 409


def test_error_reports_the_allowed_targets():
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        assert_can_transition(LeadState.REACHED_OUT, LeadState.PENDING)

    details = exc_info.value.details
    assert details["current_state"] == "REACHED_OUT"
    assert details["requested_state"] == "PENDING"
    assert details["allowed_states"] == []
