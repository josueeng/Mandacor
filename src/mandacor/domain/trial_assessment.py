from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from mandacor.domain.comparison import AngleComparison, ColorComparison
from mandacor.domain.measurements import MeasurementAngle, REQUIRED_MEASUREMENT_ANGLES


# Changes smaller than these limits are treated as measurement/application noise.
DEFAULT_DELTA_E_NOISE = 0.2
DEFAULT_AXIS_NOISE = 0.15


class TrialVerdict(str, Enum):
    IMPROVED = "improved"
    WORSENED = "worsened"
    MIXED = "mixed"
    UNCHANGED = "unchanged"


class AngleChange(str, Enum):
    IMPROVED = "improved"
    WORSENED = "worsened"
    UNCHANGED = "unchanged"


class AxisChange(str, Enum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    WORSENED_OVERSHOOT = "worsened_overshoot"
    WORSENED_WRONG_DIRECTION = "worsened_wrong_direction"


class AssessedAxis(str, Enum):
    L = "l"
    A = "a"
    B = "b"


@dataclass(frozen=True, slots=True)
class AxisAssessment:
    axis: AssessedAxis
    before_delta: float
    after_delta: float
    change: AxisChange
    crossed_target: bool

    @property
    def worsened(self) -> bool:
        return self.change in (
            AxisChange.WORSENED_OVERSHOOT,
            AxisChange.WORSENED_WRONG_DIRECTION,
        )


@dataclass(frozen=True, slots=True)
class AngleAssessment:
    angle: MeasurementAngle
    before_delta_e76: float
    after_delta_e76: float
    change: AngleChange
    axes: tuple[AxisAssessment, ...]


@dataclass(frozen=True, slots=True)
class TrialAssessment:
    """Instrument-only judgement of an adjustment; independent of operator feedback."""

    verdict: TrialVerdict
    worst_delta_e_before: float
    worst_delta_e_after: float
    improved_angles: tuple[MeasurementAngle, ...]
    worsened_angles: tuple[MeasurementAngle, ...]
    by_angle: Mapping[MeasurementAngle, AngleAssessment]
    delta_e_noise: float
    axis_noise: float

    @property
    def overshoot_detected(self) -> bool:
        return any(
            axis.change is AxisChange.WORSENED_OVERSHOOT
            for angle in self.by_angle.values()
            for axis in angle.axes
        )

    @property
    def wrong_direction_detected(self) -> bool:
        return any(
            axis.change is AxisChange.WORSENED_WRONG_DIRECTION
            for angle in self.by_angle.values()
            for axis in angle.axes
        )


def _assess_axis(
    axis: AssessedAxis, before: float, after: float, noise: float
) -> AxisAssessment:
    crossed = before * after < 0 and abs(before) > noise and abs(after) > noise
    reduction = abs(before) - abs(after)
    if reduction > noise:
        change = AxisChange.IMPROVED
    elif reduction < -noise:
        change = (
            AxisChange.WORSENED_OVERSHOOT if crossed else AxisChange.WORSENED_WRONG_DIRECTION
        )
    else:
        change = AxisChange.UNCHANGED
    return AxisAssessment(axis, before, after, change, crossed)


def _assess_angle(
    before: AngleComparison,
    after: AngleComparison,
    delta_e_noise: float,
    axis_noise: float,
) -> AngleAssessment:
    variation = after.delta_e76 - before.delta_e76
    if variation > delta_e_noise:
        change = AngleChange.WORSENED
    elif variation < -delta_e_noise:
        change = AngleChange.IMPROVED
    else:
        change = AngleChange.UNCHANGED
    axes = (
        _assess_axis(AssessedAxis.L, before.delta_l, after.delta_l, axis_noise),
        _assess_axis(AssessedAxis.A, before.delta_a, after.delta_a, axis_noise),
        _assess_axis(AssessedAxis.B, before.delta_b, after.delta_b, axis_noise),
    )
    return AngleAssessment(
        before.angle, before.delta_e76, after.delta_e76, change, axes
    )


def assess_trial(
    before_comparison: ColorComparison,
    after_comparison: ColorComparison,
    *,
    delta_e_noise: float = DEFAULT_DELTA_E_NOISE,
    axis_noise: float = DEFAULT_AXIS_NOISE,
) -> TrialAssessment:
    if delta_e_noise < 0 or axis_noise < 0:
        raise ValueError("noise limits must be non-negative")
    by_angle = {
        angle: _assess_angle(
            before_comparison.angles[angle],
            after_comparison.angles[angle],
            delta_e_noise,
            axis_noise,
        )
        for angle in REQUIRED_MEASUREMENT_ANGLES
    }
    improved = tuple(
        angle for angle, item in by_angle.items() if item.change is AngleChange.IMPROVED
    )
    worsened = tuple(
        angle for angle, item in by_angle.items() if item.change is AngleChange.WORSENED
    )
    worst_before = max(item.before_delta_e76 for item in by_angle.values())
    worst_after = max(item.after_delta_e76 for item in by_angle.values())
    # The worst angle governs approval at the bench, so its growth alone means worse.
    if worst_after - worst_before > delta_e_noise:
        verdict = TrialVerdict.WORSENED
    elif improved and worsened:
        verdict = TrialVerdict.MIXED
    elif worsened:
        verdict = TrialVerdict.WORSENED
    elif improved:
        verdict = TrialVerdict.IMPROVED
    else:
        verdict = TrialVerdict.UNCHANGED
    return TrialAssessment(
        verdict,
        worst_before,
        worst_after,
        improved,
        worsened,
        MappingProxyType(by_angle),
        delta_e_noise,
        axis_noise,
    )
