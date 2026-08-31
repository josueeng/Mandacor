from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, TypeVar

from mandacor.domain.comparison import AngleComparison, ColorComparison
from mandacor.domain.measurements import MeasurementAngle, REQUIRED_MEASUREMENT_ANGLES


class LightnessDirection(str, Enum):
    LIGHTER = "lighter"
    DARKER = "darker"
    EQUAL = "equal"
    MIXED = "mixed"


class RedGreenDirection(str, Enum):
    REDDER = "redder"
    GREENER = "greener"
    EQUAL = "equal"
    MIXED = "mixed"


class YellowBlueDirection(str, Enum):
    YELLOWER = "yellower"
    BLUER = "bluer"
    EQUAL = "equal"
    MIXED = "mixed"


class DominantAxis(str, Enum):
    L = "l"
    A = "a"
    B = "b"
    TIE = "tie"


class AxisSignPattern(str, Enum):
    POSITIVE_ACROSS_ALL = "positive_across_all"
    NEGATIVE_ACROSS_ALL = "negative_across_all"
    EQUAL_ACROSS_ALL = "equal_across_all"
    SIGN_CROSSOVER = "sign_crossover"
    MIXED_WITH_EQUAL = "mixed_with_equal"


class LightnessTrend(str, Enum):
    INCREASING_WITH_ANGLE = "increasing_with_angle"
    DECREASING_WITH_ANGLE = "decreasing_with_angle"
    CONSTANT = "constant"
    NON_MONOTONIC = "non_monotonic"


@dataclass(frozen=True, slots=True)
class AngleDiagnosis:
    angle: MeasurementAngle
    comparison: AngleComparison
    lightness_direction: LightnessDirection
    red_green_direction: RedGreenDirection
    yellow_blue_direction: YellowBlueDirection
    dominant_axis: DominantAxis

    @property
    def delta_l(self) -> float:
        return self.comparison.delta_l

    @property
    def delta_a(self) -> float:
        return self.comparison.delta_a

    @property
    def delta_b(self) -> float:
        return self.comparison.delta_b

    @property
    def delta_e76(self) -> float:
        return self.comparison.delta_e76


@dataclass(frozen=True, slots=True)
class RegionSummary:
    angles: tuple[MeasurementAngle, ...]
    lightness: LightnessDirection
    red_green: RedGreenDirection
    yellow_blue: YellowBlueDirection


@dataclass(frozen=True, slots=True)
class MultianglePatterns:
    lightness: AxisSignPattern
    red_green: AxisSignPattern
    yellow_blue: AxisSignPattern
    lightness_trend: LightnessTrend


@dataclass(frozen=True, slots=True)
class ColorDiagnosis:
    session_id: uuid.UUID
    target_measurement_id: int
    sample_measurement_id: int
    angle_diagnoses: Mapping[MeasurementAngle, AngleDiagnosis]
    worst_angle: MeasurementAngle
    angles_by_delta_e_descending: tuple[MeasurementAngle, ...]
    front_summary: RegionSummary
    mid_angle_summary: AngleDiagnosis
    flop_summary: RegionSummary
    global_patterns: MultianglePatterns
    target_guid: str | None = None
    sample_guid: str | None = None

    def __post_init__(self) -> None:
        normalized: dict[MeasurementAngle, AngleDiagnosis] = {}
        for angle in REQUIRED_MEASUREMENT_ANGLES:
            diagnosis = self.angle_diagnoses[angle]
            if diagnosis.angle is not angle:
                raise ValueError("angle diagnosis key does not match its angle")
            normalized[angle] = diagnosis
        if len(self.angle_diagnoses) != len(REQUIRED_MEASUREMENT_ANGLES):
            raise ValueError("diagnosis contains unexpected angles")
        object.__setattr__(self, "angle_diagnoses", MappingProxyType(normalized))


Direction = TypeVar("Direction", bound=Enum)


def _direction(
    value: float,
    *,
    positive: Direction,
    negative: Direction,
    equal: Direction,
) -> Direction:
    if value > 0:
        return positive
    if value < 0:
        return negative
    return equal


def _dominant_axis(comparison: AngleComparison) -> DominantAxis:
    magnitudes = {
        DominantAxis.L: abs(comparison.delta_l),
        DominantAxis.A: abs(comparison.delta_a),
        DominantAxis.B: abs(comparison.delta_b),
    }
    maximum = max(magnitudes.values())
    winners = [axis for axis, magnitude in magnitudes.items() if magnitude == maximum]
    return winners[0] if len(winners) == 1 else DominantAxis.TIE


def _angle_diagnosis(comparison: AngleComparison) -> AngleDiagnosis:
    return AngleDiagnosis(
        angle=comparison.angle,
        comparison=comparison,
        lightness_direction=_direction(
            comparison.delta_l,
            positive=LightnessDirection.LIGHTER,
            negative=LightnessDirection.DARKER,
            equal=LightnessDirection.EQUAL,
        ),
        red_green_direction=_direction(
            comparison.delta_a,
            positive=RedGreenDirection.REDDER,
            negative=RedGreenDirection.GREENER,
            equal=RedGreenDirection.EQUAL,
        ),
        yellow_blue_direction=_direction(
            comparison.delta_b,
            positive=YellowBlueDirection.YELLOWER,
            negative=YellowBlueDirection.BLUER,
            equal=YellowBlueDirection.EQUAL,
        ),
        dominant_axis=_dominant_axis(comparison),
    )


def _common_direction(values: list[Direction], mixed: Direction) -> Direction:
    first = values[0]
    return first if all(value is first for value in values[1:]) else mixed


def _region_summary(
    diagnoses: Mapping[MeasurementAngle, AngleDiagnosis],
    angles: tuple[MeasurementAngle, ...],
) -> RegionSummary:
    selected = [diagnoses[angle] for angle in angles]
    return RegionSummary(
        angles=angles,
        lightness=_common_direction(
            [item.lightness_direction for item in selected], LightnessDirection.MIXED
        ),
        red_green=_common_direction(
            [item.red_green_direction for item in selected], RedGreenDirection.MIXED
        ),
        yellow_blue=_common_direction(
            [item.yellow_blue_direction for item in selected], YellowBlueDirection.MIXED
        ),
    )


def _sign_pattern(values: list[float]) -> AxisSignPattern:
    if all(value > 0 for value in values):
        return AxisSignPattern.POSITIVE_ACROSS_ALL
    if all(value < 0 for value in values):
        return AxisSignPattern.NEGATIVE_ACROSS_ALL
    if all(value == 0 for value in values):
        return AxisSignPattern.EQUAL_ACROSS_ALL
    if any(value > 0 for value in values) and any(value < 0 for value in values):
        return AxisSignPattern.SIGN_CROSSOVER
    return AxisSignPattern.MIXED_WITH_EQUAL


def _lightness_trend(values: list[float]) -> LightnessTrend:
    if all(left < right for left, right in zip(values, values[1:])):
        return LightnessTrend.INCREASING_WITH_ANGLE
    if all(left > right for left, right in zip(values, values[1:])):
        return LightnessTrend.DECREASING_WITH_ANGLE
    if all(left == right for left, right in zip(values, values[1:])):
        return LightnessTrend.CONSTANT
    return LightnessTrend.NON_MONOTONIC


def diagnose_comparison(comparison: ColorComparison) -> ColorDiagnosis:
    diagnoses = {
        angle: _angle_diagnosis(comparison.angles[angle])
        for angle in REQUIRED_MEASUREMENT_ANGLES
    }
    ranking = tuple(
        sorted(
            REQUIRED_MEASUREMENT_ANGLES,
            key=lambda angle: (-comparison.angles[angle].delta_e76, int(angle)),
        )
    )
    delta_l_values = [comparison.angles[angle].delta_l for angle in REQUIRED_MEASUREMENT_ANGLES]
    delta_a_values = [comparison.angles[angle].delta_a for angle in REQUIRED_MEASUREMENT_ANGLES]
    delta_b_values = [comparison.angles[angle].delta_b for angle in REQUIRED_MEASUREMENT_ANGLES]
    return ColorDiagnosis(
        session_id=comparison.session_id,
        target_measurement_id=comparison.target_measurement_id,
        sample_measurement_id=comparison.sample_measurement_id,
        target_guid=comparison.target_guid,
        sample_guid=comparison.sample_guid,
        angle_diagnoses=diagnoses,
        worst_angle=ranking[0],
        angles_by_delta_e_descending=ranking,
        front_summary=_region_summary(
            diagnoses, (MeasurementAngle.DEG_15, MeasurementAngle.DEG_25)
        ),
        mid_angle_summary=diagnoses[MeasurementAngle.DEG_45],
        flop_summary=_region_summary(
            diagnoses, (MeasurementAngle.DEG_75, MeasurementAngle.DEG_105)
        ),
        global_patterns=MultianglePatterns(
            lightness=_sign_pattern(delta_l_values),
            red_green=_sign_pattern(delta_a_values),
            yellow_blue=_sign_pattern(delta_b_values),
            lightness_trend=_lightness_trend(delta_l_values),
        ),
    )
