from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

from mandacor.domain.comparison import ColorComparison, compare_measurements
from mandacor.domain.diagnosis import diagnose_comparison
from mandacor.domain.measurements import Measurement, MeasurementAngle, REQUIRED_MEASUREMENT_ANGLES
from mandacor.domain.pigments import PaintContext, PigmentKnowledgeBase
from mandacor.domain.sessions import ColorSession, SessionState
from mandacor.domain.trial_assessment import TrialAssessment, TrialVerdict, assess_trial


class AdjustmentError(ValueError):
    pass


class AdjustmentLifecycle(str, Enum):
    PLANNED = "planned"
    APPLIED_WAITING_FOR_AFTER = "applied_waiting_for_after"
    COMPLETED = "completed"
    CANCELLED_BEFORE_APPLICATION = "cancelled_before_application"
    ABANDONED_AFTER_APPLICATION = "abandoned_after_application"


class LearningEligibility(str, Enum):
    ISOLATED_SINGLE_COMPONENT = "isolated_single_component"
    MIXED_COMPONENTS = "mixed_components"


class OutcomeDirection(str, Enum):
    IMPROVED = "improved"
    WORSENED = "worsened"
    UNCHANGED = "unchanged"


class VisualResult(str, Enum):
    BETTER = "better"
    WORSE = "worse"
    SAME = "same"
    UNKNOWN = "unknown"


class OperatorTrialStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class DataQualityFlag(str, Enum):
    COMPLETE = "complete"
    MISSING_OPERATOR_FEEDBACK = "missing_operator_feedback"
    MIXED_COMPONENTS = "mixed_components"
    ABANDONED = "abandoned"


def _positive_decimal(value: object, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise AdjustmentError(f"{field_name} must be a positive finite decimal")
    try:
        converted = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise AdjustmentError(f"{field_name} must be a positive finite decimal") from error
    if not converted.is_finite() or converted <= 0:
        raise AdjustmentError(f"{field_name} must be greater than zero")
    return converted


def _same_measurement(left: Measurement, right: Measurement) -> bool:
    if left.measurement_id != right.measurement_id:
        return False
    if left.guid is not None and right.guid is not None:
        return left.guid == right.guid
    return True


def _validate_instrument(serial: str | None, measurement: Measurement, *, role: str) -> None:
    if serial is not None and measurement.instrument_serial is not None:
        if serial != measurement.instrument_serial:
            raise AdjustmentError(f"{role} belongs to another instrument")


@dataclass(frozen=True, slots=True)
class AdjustmentComponent:
    pigment_code: str
    quantity_g: Decimal

    def __post_init__(self) -> None:
        code = self.pigment_code.strip().upper()
        if not code:
            raise AdjustmentError("pigment_code cannot be empty")
        object.__setattr__(self, "pigment_code", code)
        object.__setattr__(
            self, "quantity_g", _positive_decimal(self.quantity_g, field_name="quantity_g")
        )


@dataclass(frozen=True, slots=True)
class AngleObservedResponse:
    angle: MeasurementAngle
    response_l: float
    response_a: float
    response_b: float


@dataclass(frozen=True, slots=True)
class AngleAdjustmentOutcome:
    angle: MeasurementAngle
    before_delta_e76: float
    after_delta_e76: float
    delta_e_improvement: float
    before_abs_delta_l: float
    after_abs_delta_l: float
    improvement_l: float
    lightness_outcome: OutcomeDirection
    before_abs_delta_a: float
    after_abs_delta_a: float
    improvement_a: float
    red_green_outcome: OutcomeDirection
    before_abs_delta_b: float
    after_abs_delta_b: float
    improvement_b: float
    yellow_blue_outcome: OutcomeDirection
    delta_e_outcome: OutcomeDirection


@dataclass(frozen=True, slots=True)
class PendingAdjustment:
    adjustment_id: uuid.UUID
    session_id: uuid.UUID
    instrument_serial: str | None
    target: Measurement
    before: Measurement
    paint_context: PaintContext
    volume_ml: Decimal
    components: tuple[AdjustmentComponent, ...]
    operator_reason: str
    lifecycle: AdjustmentLifecycle
    created_at: datetime
    applied_at: datetime | None = None
    observations: str | None = None
    base_identifier: str | None = None
    color_description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "volume_ml", _positive_decimal(self.volume_ml, field_name="volume_ml")
        )
        object.__setattr__(self, "components", tuple(self.components))
        if not self.components:
            raise AdjustmentError("at least one adjustment component is required")
        if not all(isinstance(item, AdjustmentComponent) for item in self.components):
            raise AdjustmentError("components must contain AdjustmentComponent values")
        codes = [item.pigment_code for item in self.components]
        if len(codes) != len(set(codes)):
            raise AdjustmentError("duplicate pigment codes must be combined explicitly")
        if _same_measurement(self.target, self.before):
            raise AdjustmentError("target and before must be distinct measurements")
        _validate_instrument(self.instrument_serial, self.target, role="target")
        _validate_instrument(self.instrument_serial, self.before, role="before")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise AdjustmentError("created_at must be timezone-aware")
        if self.lifecycle is AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER:
            if self.applied_at is None:
                raise AdjustmentError("applied adjustment requires applied_at")

    @property
    def learning_eligibility(self) -> LearningEligibility:
        if len(self.components) == 1:
            return LearningEligibility.ISOLATED_SINGLE_COMPONENT
        return LearningEligibility.MIXED_COMPONENTS

    def confirm_applied(
        self,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> "PendingAdjustment":
        if self.lifecycle is not AdjustmentLifecycle.PLANNED:
            raise AdjustmentError("only a planned adjustment can be confirmed applied")
        return replace(
            self,
            lifecycle=AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER,
            applied_at=now(),
        )

    def cancel_before_application(self) -> "PendingAdjustment":
        if self.lifecycle is not AdjustmentLifecycle.PLANNED:
            raise AdjustmentError("applied adjustments cannot be cancelled as unapplied")
        return replace(self, lifecycle=AdjustmentLifecycle.CANCELLED_BEFORE_APPLICATION)

    def abandon_after_application(self, observation: str) -> "PendingAdjustment":
        if self.lifecycle is not AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER:
            raise AdjustmentError("only an applied pending adjustment can be abandoned")
        if not observation.strip():
            raise AdjustmentError("abandonment requires an explicit observation")
        return replace(
            self,
            lifecycle=AdjustmentLifecycle.ABANDONED_AFTER_APPLICATION,
            observations=observation.strip(),
        )


@dataclass(frozen=True, slots=True)
class CompletedAdjustmentTrial:
    adjustment_id: uuid.UUID
    session_id: uuid.UUID
    instrument_serial: str | None
    target: Measurement
    before: Measurement
    after: Measurement
    paint_context: PaintContext
    volume_ml: Decimal
    components: tuple[AdjustmentComponent, ...]
    operator_reason: str
    observed_response_by_angle: Mapping[MeasurementAngle, AngleObservedResponse]
    before_comparison: ColorComparison
    after_comparison: ColorComparison
    outcome_by_angle: Mapping[MeasurementAngle, AngleAdjustmentOutcome]
    worst_angle_before: MeasurementAngle
    worst_angle_after: MeasurementAngle
    learning_eligibility: LearningEligibility
    visual_result: VisualResult
    operator_status: OperatorTrialStatus
    observations: str | None
    created_at: datetime
    applied_at: datetime
    completed_at: datetime
    lifecycle: AdjustmentLifecycle = AdjustmentLifecycle.COMPLETED
    base_identifier: str | None = None
    color_description: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("observed_response_by_angle", "outcome_by_angle"):
            values = getattr(self, field_name)
            normalized = {angle: values[angle] for angle in REQUIRED_MEASUREMENT_ANGLES}
            if len(values) != len(REQUIRED_MEASUREMENT_ANGLES):
                raise AdjustmentError(f"{field_name} contains unexpected angles")
            object.__setattr__(self, field_name, MappingProxyType(normalized))
        object.__setattr__(self, "components", tuple(self.components))
        if self.lifecycle is not AdjustmentLifecycle.COMPLETED:
            raise AdjustmentError("completed trial must have completed lifecycle")

    @property
    def assessment(self) -> TrialAssessment:
        return assess_trial(self.before_comparison, self.after_comparison)

    @property
    def operator_disagrees_with_instrument(self) -> bool:
        verdict = self.assessment.verdict
        return (
            (self.visual_result is VisualResult.BETTER and verdict is TrialVerdict.WORSENED)
            or (self.visual_result is VisualResult.WORSE and verdict is TrialVerdict.IMPROVED)
        )

    @property
    def data_quality_flags(self) -> frozenset[DataQualityFlag]:
        flags = {DataQualityFlag.COMPLETE}
        if self.visual_result is VisualResult.UNKNOWN or self.operator_status is OperatorTrialStatus.UNKNOWN:
            flags.add(DataQualityFlag.MISSING_OPERATOR_FEEDBACK)
        if self.learning_eligibility is LearningEligibility.MIXED_COMPONENTS:
            flags.add(DataQualityFlag.MIXED_COMPONENTS)
        return frozenset(flags)

    def with_operator_feedback(
        self,
        *,
        visual_result: VisualResult,
        operator_status: OperatorTrialStatus,
        observations: str | None = None,
    ) -> "CompletedAdjustmentTrial":
        if not isinstance(visual_result, VisualResult):
            raise AdjustmentError("visual_result must be a VisualResult")
        if not isinstance(operator_status, OperatorTrialStatus):
            raise AdjustmentError("operator_status must be an OperatorTrialStatus")
        normalized_observations = observations.strip() if observations else None
        return replace(
            self,
            visual_result=visual_result,
            operator_status=operator_status,
            observations=normalized_observations or None,
        )


@dataclass(frozen=True, slots=True)
class AdjustmentHistory:
    trials: tuple[CompletedAdjustmentTrial, ...] = ()

    def append(self, trial: CompletedAdjustmentTrial) -> "AdjustmentHistory":
        if any(item.adjustment_id == trial.adjustment_id for item in self.trials):
            raise AdjustmentError("adjustment is already present in history")
        if self.trials:
            previous = self.trials[-1]
            if previous.session_id == trial.session_id and not _same_measurement(previous.after, trial.before):
                raise AdjustmentError("sequential trial must start from the previous after")
        return AdjustmentHistory(self.trials + (trial,))


def plan_adjustment(
    session: ColorSession,
    paint_context: PaintContext,
    volume_ml: object,
    components: tuple[AdjustmentComponent, ...],
    operator_reason: str,
    knowledge_base: PigmentKnowledgeBase,
    *,
    adjustment_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    base_identifier: str | None = None,
    color_description: str | None = None,
) -> PendingAdjustment:
    if session.state is not SessionState.READY_FOR_COMPARISON:
        raise AdjustmentError("session must be ready with target and current sample")
    assert session.target is not None and session.sample is not None
    for component in components:
        if component.pigment_code not in knowledge_base.profiles:
            raise AdjustmentError(f"unknown pigment code: {component.pigment_code}")
    return PendingAdjustment(
        adjustment_id_factory(), session.session_id, session.instrument_serial,
        session.target, session.sample, paint_context,
        _positive_decimal(volume_ml, field_name="volume_ml"), tuple(components),
        operator_reason.strip(), AdjustmentLifecycle.PLANNED, now(),
        base_identifier=base_identifier, color_description=color_description,
    )


def calculate_observed_response(
    before: Measurement,
    after: Measurement,
) -> Mapping[MeasurementAngle, AngleObservedResponse]:
    response = {
        angle: AngleObservedResponse(
            angle,
            after.angles[angle].L - before.angles[angle].L,
            after.angles[angle].a - before.angles[angle].a,
            after.angles[angle].b - before.angles[angle].b,
        )
        for angle in REQUIRED_MEASUREMENT_ANGLES
    }
    return MappingProxyType(response)


def _outcome(value: float) -> OutcomeDirection:
    if value > 0:
        return OutcomeDirection.IMPROVED
    if value < 0:
        return OutcomeDirection.WORSENED
    return OutcomeDirection.UNCHANGED


def calculate_adjustment_outcome(
    before_comparison: ColorComparison,
    after_comparison: ColorComparison,
) -> Mapping[MeasurementAngle, AngleAdjustmentOutcome]:
    if (
        before_comparison.session_id != after_comparison.session_id
        or before_comparison.target_measurement_id != after_comparison.target_measurement_id
    ):
        raise AdjustmentError("before and after comparisons must share session and target")
    outcomes: dict[MeasurementAngle, AngleAdjustmentOutcome] = {}
    for angle in REQUIRED_MEASUREMENT_ANGLES:
        before = before_comparison.angles[angle]
        after = after_comparison.angles[angle]
        improvement_l = abs(before.delta_l) - abs(after.delta_l)
        improvement_a = abs(before.delta_a) - abs(after.delta_a)
        improvement_b = abs(before.delta_b) - abs(after.delta_b)
        improvement_e = before.delta_e76 - after.delta_e76
        outcomes[angle] = AngleAdjustmentOutcome(
            angle, before.delta_e76, after.delta_e76, improvement_e,
            abs(before.delta_l), abs(after.delta_l), improvement_l, _outcome(improvement_l),
            abs(before.delta_a), abs(after.delta_a), improvement_a, _outcome(improvement_a),
            abs(before.delta_b), abs(after.delta_b), improvement_b, _outcome(improvement_b),
            _outcome(improvement_e),
        )
    return MappingProxyType(outcomes)


def complete_adjustment_trial(
    pending: PendingAdjustment,
    after: Measurement,
    *,
    visual_result: VisualResult = VisualResult.UNKNOWN,
    operator_status: OperatorTrialStatus = OperatorTrialStatus.UNKNOWN,
    observations: str | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> CompletedAdjustmentTrial:
    if pending.lifecycle is not AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER:
        raise AdjustmentError("adjustment must be applied before completion")
    if _same_measurement(pending.before, after):
        raise AdjustmentError("after must be a new measurement, not before")
    _validate_instrument(pending.instrument_serial, after, role="after")
    before_comparison = compare_measurements(pending.session_id, pending.target, pending.before)
    after_comparison = compare_measurements(pending.session_id, pending.target, after)
    responses = calculate_observed_response(pending.before, after)
    outcomes = calculate_adjustment_outcome(before_comparison, after_comparison)
    return CompletedAdjustmentTrial(
        pending.adjustment_id, pending.session_id, pending.instrument_serial,
        pending.target, pending.before, after, pending.paint_context, pending.volume_ml,
        pending.components, pending.operator_reason, responses, before_comparison,
        after_comparison, outcomes,
        diagnose_comparison(before_comparison).worst_angle,
        diagnose_comparison(after_comparison).worst_angle,
        pending.learning_eligibility, visual_result, operator_status,
        observations, pending.created_at, pending.applied_at, now(),
        base_identifier=pending.base_identifier,
        color_description=pending.color_description,
    )


VOLUME_HALF_QUARTER_ML = Decimal("450")
VOLUME_QUARTER_ML = Decimal("900")
VOLUME_GALLON_ML = Decimal("3600")
