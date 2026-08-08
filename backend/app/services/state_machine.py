"""Lead state transitions.

Keeping the legal moves in one explicit table means the rule lives in exactly
one place, and adding a state later is a change to this dict rather than a hunt
through the route handlers.
"""

from __future__ import annotations

from types import MappingProxyType

from app.core.errors import InvalidStateTransitionError
from app.models.enums import LeadState

ALLOWED_TRANSITIONS: MappingProxyType[LeadState, frozenset[LeadState]] = MappingProxyType(
    {
        LeadState.PENDING: frozenset({LeadState.REACHED_OUT}),
        # Terminal today. REACHED_OUT -> PENDING is intentionally not allowed:
        # "we un-contacted them" isn't a real event, and the audit trail would
        # be misleading.
        LeadState.REACHED_OUT: frozenset(),
    }
)


def can_transition(current: LeadState, target: LeadState) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def assert_can_transition(current: LeadState, target: LeadState) -> None:
    """Raise InvalidStateTransitionError (409) unless the move is legal."""
    if current == target:
        raise InvalidStateTransitionError(
            f"Lead is already in {target.value}.",
            details={"current_state": current.value, "requested_state": target.value},
        )

    if not can_transition(current, target):
        allowed = sorted(s.value for s in ALLOWED_TRANSITIONS.get(current, frozenset()))
        raise InvalidStateTransitionError(
            f"Cannot move a lead from {current.value} to {target.value}.",
            details={
                "current_state": current.value,
                "requested_state": target.value,
                "allowed_states": allowed,
            },
        )
