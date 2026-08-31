from __future__ import annotations

from mandacor.domain.comparison import ColorComparison, compare_measurements
from mandacor.domain.sessions import ColorSession, InvalidSessionStateError, SessionState


def compare_session(session: ColorSession) -> ColorComparison:
    if (
        session.state is not SessionState.READY_FOR_COMPARISON
        or session.target is None
        or session.sample is None
    ):
        raise InvalidSessionStateError(
            "session must be ready for comparison with target and sample"
        )
    return compare_measurements(session.session_id, session.target, session.sample)
