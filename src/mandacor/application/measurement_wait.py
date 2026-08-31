from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from mandacor.config import (
    DEFAULT_CANDIDATE_STABILIZATION_INTERVAL_SECONDS,
    DEFAULT_CANDIDATE_STABILIZATION_RETRIES,
    DEFAULT_MAX_TRANSIENT_POLL_ERRORS,
    DEFAULT_MEASUREMENT_POLL_INTERVAL_SECONDS,
    DEFAULT_MEASUREMENT_WAIT_TIMEOUT_SECONDS,
)
from mandacor.domain.instruments import InstrumentInfo
from mandacor.domain.measurements import Measurement, MeasurementError, MeasurementReference
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentTimeoutError
from mandacor.ports.instrument import InstrumentAdapter


logger = logging.getLogger(__name__)


class MeasurementWaitError(Exception):
    pass


class NewMeasurementTimeoutError(MeasurementWaitError):
    def __init__(
        self,
        *,
        elapsed: float,
        known_count: int,
        last_observed_count: int,
        poll_count: int,
    ) -> None:
        self.elapsed = elapsed
        self.known_count = known_count
        self.last_observed_count = last_observed_count
        self.poll_count = poll_count
        super().__init__(
            f"no new measurement detected within {elapsed:.3f}s "
            f"(known={known_count}, observed={last_observed_count}, polls={poll_count})"
        )


class MeasurementWaitCancelledError(MeasurementWaitError):
    pass


class InstrumentChangedDuringWaitError(MeasurementWaitError):
    pass


@dataclass(frozen=True, slots=True)
class MeasurementIdentity:
    instrument_serial: str | None
    measurement_id: int
    guid: str | None


@dataclass(frozen=True, slots=True)
class MeasurementSnapshot:
    identities: frozenset[MeasurementIdentity]
    instrument_serial: str | None
    created_at: datetime
    session_id: uuid.UUID

    @property
    def known_ids(self) -> frozenset[int]:
        return frozenset(identity.measurement_id for identity in self.identities)

    def contains(self, measurement: Measurement) -> bool:
        identity = MeasurementIdentity(
            instrument_serial=measurement.instrument_serial or self.instrument_serial,
            measurement_id=measurement.measurement_id,
            guid=measurement.guid,
        )
        return MeasurementWaitService._is_known(identity, self.identities)


WaitFunction = Callable[[float, threading.Event | None], bool]


def _default_wait(seconds: float, cancellation: threading.Event | None) -> bool:
    if cancellation is not None:
        return cancellation.wait(seconds)
    time.sleep(seconds)
    return False


class MeasurementWaitService:
    def __init__(
        self,
        adapter: InstrumentAdapter,
        instrument_info: InstrumentInfo,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        waiter: WaitFunction = _default_wait,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._adapter = adapter
        self._instrument_info = instrument_info
        self._monotonic = monotonic
        self._wait = waiter
        self._now = now
        self._session_id = uuid.uuid4()

    def _identity_from_reference(self, reference: MeasurementReference) -> MeasurementIdentity:
        return MeasurementIdentity(
            instrument_serial=self._instrument_info.serial,
            measurement_id=reference.measurement_id,
            guid=reference.guid,
        )

    @staticmethod
    def _is_known(
        identity: MeasurementIdentity,
        known_identities: frozenset[MeasurementIdentity],
    ) -> bool:
        for known in known_identities:
            if (
                known.instrument_serial != identity.instrument_serial
                or known.measurement_id != identity.measurement_id
            ):
                continue
            if known.guid is not None and identity.guid is not None:
                return known.guid == identity.guid
            return True
        return False

    def create_snapshot(self) -> MeasurementSnapshot:
        references = self._adapter.list_measurements()
        identities = frozenset(self._identity_from_reference(reference) for reference in references)
        logger.debug(
            "measurement snapshot created",
            extra={"known_ids": sorted(identity.measurement_id for identity in identities)},
        )
        return MeasurementSnapshot(
            identities=identities,
            instrument_serial=self._instrument_info.serial,
            created_at=self._now(),
            session_id=self._session_id,
        )

    def _validate_session(self, snapshot: MeasurementSnapshot) -> None:
        if snapshot.session_id != self._session_id:
            raise InstrumentChangedDuringWaitError(
                "snapshot belongs to another instrument connection session"
            )
        if snapshot.instrument_serial != self._instrument_info.serial:
            raise InstrumentChangedDuringWaitError(
                "instrument serial changed after measurement snapshot"
            )

    def wait_for_new_measurement(
        self,
        snapshot: MeasurementSnapshot,
        *,
        timeout: float = DEFAULT_MEASUREMENT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_MEASUREMENT_POLL_INTERVAL_SECONDS,
        cancellation: threading.Event | None = None,
        max_transient_poll_errors: int = DEFAULT_MAX_TRANSIENT_POLL_ERRORS,
        candidate_stabilization_retries: int = DEFAULT_CANDIDATE_STABILIZATION_RETRIES,
        candidate_stabilization_interval: float = (
            DEFAULT_CANDIDATE_STABILIZATION_INTERVAL_SECONDS
        ),
    ) -> Measurement:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        if max_transient_poll_errors < 0:
            raise ValueError("max_transient_poll_errors must be non-negative")
        if candidate_stabilization_retries < 0:
            raise ValueError("candidate_stabilization_retries must be non-negative")
        if candidate_stabilization_interval <= 0:
            raise ValueError("candidate_stabilization_interval must be greater than zero")
        self._validate_session(snapshot)
        if cancellation is not None and cancellation.is_set():
            raise MeasurementWaitCancelledError("measurement wait cancelled")

        start = self._monotonic()
        deadline = start + timeout
        seen_during_wait: set[MeasurementIdentity] = set()
        processed_candidates: set[MeasurementIdentity] = set()
        poll_count = 0
        last_observed_count = len(snapshot.identities)
        consecutive_poll_errors = 0
        logger.info(
            "waiting for new measurement",
            extra={"known_count": len(snapshot.identities), "timeout": timeout},
        )

        while True:
            self._validate_session(snapshot)
            if cancellation is not None and cancellation.is_set():
                raise MeasurementWaitCancelledError("measurement wait cancelled")
            now = self._monotonic()
            if now >= deadline:
                raise NewMeasurementTimeoutError(
                    elapsed=now - start,
                    known_count=len(snapshot.identities),
                    last_observed_count=last_observed_count,
                    poll_count=poll_count,
                )

            poll_count += 1
            try:
                references = self._adapter.list_measurements()
            except InstrumentTimeoutError:
                consecutive_poll_errors += 1
                logger.warning(
                    "temporary measurement poll timeout",
                    extra={
                        "poll_number": poll_count,
                        "consecutive_errors": consecutive_poll_errors,
                    },
                )
                if consecutive_poll_errors > max_transient_poll_errors:
                    raise
                references = None
            else:
                consecutive_poll_errors = 0

            if references is not None:
                current = [
                    (reference, self._identity_from_reference(reference))
                    for reference in references
                ]
                last_observed_count = len({identity for _, identity in current})
                disappeared = [
                    known
                    for known in snapshot.identities
                    if not self._is_known(known, frozenset(identity for _, identity in current))
                ]
                if disappeared:
                    logger.warning(
                        "measurements present in snapshot disappeared",
                        extra={"measurement_ids": sorted(item.measurement_id for item in disappeared)},
                    )
                new_by_identity: dict[
                    MeasurementIdentity, MeasurementReference
                ] = {}
                for reference, identity in current:
                    if self._is_known(identity, snapshot.identities):
                        continue
                    new_by_identity.setdefault(identity, reference)
                candidates: list[tuple[MeasurementReference, MeasurementIdentity]] = []
                pending: list[MeasurementIdentity] = []
                for identity, reference in new_by_identity.items():
                    if identity in processed_candidates:
                        continue
                    if identity not in seen_during_wait:
                        seen_during_wait.add(identity)
                        pending.append(identity)
                        continue
                    candidates.append((reference, identity))
                candidates.sort(
                    key=lambda item: (item[0].measurement_id, item[0].guid or "")
                )
                logger.debug(
                    "measurement poll",
                    extra={
                        "poll_number": poll_count,
                        "current_ids": [item.measurement_id for item in references],
                        "pending_ids": sorted(item.measurement_id for item in pending),
                        "candidate_ids": [item.measurement_id for item, _ in candidates],
                    },
                )
                for reference, identity in candidates:
                    processed_candidates.add(identity)
                    measurement: Measurement | None = None
                    last_candidate_error: MeasurementError | None = None
                    attempts = 0
                    for retry_number in range(candidate_stabilization_retries + 1):
                        if self._monotonic() >= deadline:
                            break
                        attempts += 1
                        try:
                            measurement = self._adapter.get_measurement(
                                reference.measurement_id
                            )
                        except MeasurementError as error:
                            last_candidate_error = error
                            if retry_number >= candidate_stabilization_retries:
                                break
                            remaining = deadline - self._monotonic()
                            if remaining <= 0:
                                break
                            retry_delay = min(
                                candidate_stabilization_interval, remaining
                            )
                            logger.debug(
                                "new measurement candidate not stable; retrying",
                                extra={
                                    "measurement_id": reference.measurement_id,
                                    "retry_number": retry_number + 1,
                                    "retry_delay": retry_delay,
                                },
                            )
                            if self._wait(retry_delay, cancellation):
                                raise MeasurementWaitCancelledError(
                                    "measurement wait cancelled"
                                )
                            continue
                        break
                    if measurement is None:
                        logger.warning(
                            "new measurement candidate did not stabilize",
                            extra={
                                "measurement_id": reference.measurement_id,
                                "attempts": attempts,
                                "error": (
                                    str(last_candidate_error)
                                    if last_candidate_error is not None
                                    else "global timeout reached"
                                ),
                            },
                        )
                        continue
                    if self._monotonic() > deadline:
                        continue
                    measurement_serial = (
                        measurement.instrument_serial or self._instrument_info.serial
                    )
                    if (
                        snapshot.instrument_serial is not None
                        and measurement_serial is not None
                        and measurement_serial != snapshot.instrument_serial
                    ):
                        raise InstrumentChangedDuringWaitError(
                            "retrieved measurement belongs to another instrument"
                        )
                    retrieved_identity = MeasurementIdentity(
                        instrument_serial=measurement_serial,
                        measurement_id=measurement.measurement_id,
                        guid=measurement.guid,
                    )
                    if self._is_known(retrieved_identity, snapshot.identities):
                        logger.warning(
                            "candidate resolved to a measurement already present in snapshot",
                            extra={"measurement_id": measurement.measurement_id},
                        )
                        continue
                    logger.info(
                        "new measurement validated",
                        extra={"measurement_id": measurement.measurement_id},
                    )
                    return measurement

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                continue
            wait_seconds = min(poll_interval, remaining)
            logger.debug("measurement poll sleep", extra={"seconds": wait_seconds})
            if self._wait(wait_seconds, cancellation):
                raise MeasurementWaitCancelledError("measurement wait cancelled")
