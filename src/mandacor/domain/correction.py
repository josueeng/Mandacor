from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, TypeVar

from mandacor.domain.comparison import ColorComparison
from mandacor.domain.diagnosis import (
    ColorDiagnosis,
    DominantAxis,
    LightnessDirection,
    RedGreenDirection,
    YellowBlueDirection,
)
from mandacor.domain.measurements import MeasurementAngle, REQUIRED_MEASUREMENT_ANGLES


class LightnessAction(str, Enum):
    LIGHTEN = "lighten"
    DARKEN = "darken"
    NONE = "none"
    MIXED = "mixed"


class RedGreenAction(str, Enum):
    MOVE_REDDER = "move_redder"
    MOVE_GREENER = "move_greener"
    NONE = "none"
    MIXED = "mixed"


class YellowBlueAction(str, Enum):
    MOVE_YELLOWER = "move_yellower"
    MOVE_BLUER = "move_bluer"
    NONE = "none"
    MIXED = "mixed"


class Uniformity(str, Enum):
    UNIFORM = "uniform"
    MIXED = "mixed"


class AngleGroup(str, Enum):
    FRONT = "front"
    MID = "mid"
    FLOP = "flop"


CorrectionAction = LightnessAction | RedGreenAction | YellowBlueAction
Action = TypeVar("Action", bound=Enum)


@dataclass(frozen=True, slots=True)
class AngleCorrectionNeed:
    angle: MeasurementAngle
    lightness_action: LightnessAction
    red_green_action: RedGreenAction
    yellow_blue_action: YellowBlueAction
    correction_delta_l: float
    correction_delta_a: float
    correction_delta_b: float
    dominant_problem_axis: DominantAxis
    delta_e76: float


@dataclass(frozen=True, slots=True)
class CorrectionRegionSummary:
    angles: tuple[MeasurementAngle, ...]
    lightness_action: LightnessAction
    red_green_action: RedGreenAction
    yellow_blue_action: YellowBlueAction


@dataclass(frozen=True, slots=True)
class GlobalUniformity:
    lightness: Uniformity
    red_green: Uniformity
    yellow_blue: Uniformity


@dataclass(frozen=True, slots=True)
class MultiangleCorrectionFlags:
    lightness_action_varies_by_angle: bool
    red_green_action_varies_by_angle: bool
    yellow_blue_action_varies_by_angle: bool

    @property
    def multiangle_lightness_mismatch(self) -> bool:
        return self.lightness_action_varies_by_angle


@dataclass(frozen=True, slots=True)
class PrimaryIssue:
    angle: MeasurementAngle
    group: AngleGroup
    axis: DominantAxis
    action: CorrectionAction | None


@dataclass(frozen=True, slots=True)
class ColorCorrectionNeed:
    session_id: uuid.UUID
    target_measurement_id: int
    sample_measurement_id: int
    by_angle: Mapping[MeasurementAngle, AngleCorrectionNeed]
    front: CorrectionRegionSummary
    mid: AngleCorrectionNeed
    flop: CorrectionRegionSummary
    global_actions: CorrectionRegionSummary
    global_uniformity: GlobalUniformity
    worst_angle: MeasurementAngle
    primary_issue: PrimaryIssue
    multiangle_flags: MultiangleCorrectionFlags
    target_guid: str | None = None
    sample_guid: str | None = None

    def __post_init__(self) -> None:
        normalized: dict[MeasurementAngle, AngleCorrectionNeed] = {}
        for angle in REQUIRED_MEASUREMENT_ANGLES:
            item = self.by_angle[angle]
            if item.angle is not angle:
                raise ValueError("angle correction key does not match its angle")
            normalized[angle] = item
        if len(self.by_angle) != len(REQUIRED_MEASUREMENT_ANGLES):
            raise ValueError("correction need contains unexpected angles")
        object.__setattr__(self, "by_angle", MappingProxyType(normalized))

    def is_uniform_across_angles(self, axis: DominantAxis) -> bool:
        if axis is DominantAxis.L:
            return self.global_uniformity.lightness is Uniformity.UNIFORM
        if axis is DominantAxis.A:
            return self.global_uniformity.red_green is Uniformity.UNIFORM
        if axis is DominantAxis.B:
            return self.global_uniformity.yellow_blue is Uniformity.UNIFORM
        raise ValueError("uniformity is defined only for L, a, or b")


def _lightness_action(direction: LightnessDirection) -> LightnessAction:
    actions = {
        LightnessDirection.DARKER: LightnessAction.LIGHTEN,
        LightnessDirection.LIGHTER: LightnessAction.DARKEN,
        LightnessDirection.EQUAL: LightnessAction.NONE,
    }
    try:
        return actions[direction]
    except KeyError as error:
        raise ValueError("an individual angle cannot have mixed lightness") from error


def _red_green_action(direction: RedGreenDirection) -> RedGreenAction:
    actions = {
        RedGreenDirection.REDDER: RedGreenAction.MOVE_GREENER,
        RedGreenDirection.GREENER: RedGreenAction.MOVE_REDDER,
        RedGreenDirection.EQUAL: RedGreenAction.NONE,
    }
    try:
        return actions[direction]
    except KeyError as error:
        raise ValueError("an individual angle cannot have mixed red/green") from error


def _yellow_blue_action(direction: YellowBlueDirection) -> YellowBlueAction:
    actions = {
        YellowBlueDirection.YELLOWER: YellowBlueAction.MOVE_BLUER,
        YellowBlueDirection.BLUER: YellowBlueAction.MOVE_YELLOWER,
        YellowBlueDirection.EQUAL: YellowBlueAction.NONE,
    }
    try:
        return actions[direction]
    except KeyError as error:
        raise ValueError("an individual angle cannot have mixed yellow/blue") from error


def _common_action(values: list[Action], mixed: Action) -> Action:
    first = values[0]
    return first if all(value is first for value in values[1:]) else mixed


def _summary(
    needs: Mapping[MeasurementAngle, AngleCorrectionNeed],
    angles: tuple[MeasurementAngle, ...],
) -> CorrectionRegionSummary:
    selected = [needs[angle] for angle in angles]
    return CorrectionRegionSummary(
        angles=angles,
        lightness_action=_common_action(
            [item.lightness_action for item in selected], LightnessAction.MIXED
        ),
        red_green_action=_common_action(
            [item.red_green_action for item in selected], RedGreenAction.MIXED
        ),
        yellow_blue_action=_common_action(
            [item.yellow_blue_action for item in selected], YellowBlueAction.MIXED
        ),
    )


def _group_for_angle(angle: MeasurementAngle) -> AngleGroup:
    if angle in (MeasurementAngle.DEG_15, MeasurementAngle.DEG_25):
        return AngleGroup.FRONT
    if angle is MeasurementAngle.DEG_45:
        return AngleGroup.MID
    return AngleGroup.FLOP


def _primary_action(need: AngleCorrectionNeed) -> CorrectionAction | None:
    if need.dominant_problem_axis is DominantAxis.L:
        return need.lightness_action
    if need.dominant_problem_axis is DominantAxis.A:
        return need.red_green_action
    if need.dominant_problem_axis is DominantAxis.B:
        return need.yellow_blue_action
    return None


def derive_correction_need(
    diagnosis: ColorDiagnosis,
    comparison: ColorComparison,
) -> ColorCorrectionNeed:
    """Derive the required Lab movement without recommending a physical action."""
    identity_fields = (
        "session_id",
        "target_measurement_id",
        "sample_measurement_id",
        "target_guid",
        "sample_guid",
    )
    if any(getattr(diagnosis, field) != getattr(comparison, field) for field in identity_fields):
        raise ValueError("diagnosis and comparison refer to different measurements")

    needs: dict[MeasurementAngle, AngleCorrectionNeed] = {}
    for angle in REQUIRED_MEASUREMENT_ANGLES:
        observed = diagnosis.angle_diagnoses[angle]
        delta = comparison.angles[angle]
        if observed.comparison != delta:
            raise ValueError(f"diagnosis and comparison disagree at {int(angle)} degrees")
        needs[angle] = AngleCorrectionNeed(
            angle=angle,
            lightness_action=_lightness_action(observed.lightness_direction),
            red_green_action=_red_green_action(observed.red_green_direction),
            yellow_blue_action=_yellow_blue_action(observed.yellow_blue_direction),
            correction_delta_l=-delta.delta_l,
            correction_delta_a=-delta.delta_a,
            correction_delta_b=-delta.delta_b,
            dominant_problem_axis=observed.dominant_axis,
            delta_e76=delta.delta_e76,
        )

    all_angles = tuple(REQUIRED_MEASUREMENT_ANGLES)
    global_actions = _summary(needs, all_angles)
    global_uniformity = GlobalUniformity(
        lightness=(
            Uniformity.UNIFORM
            if global_actions.lightness_action is not LightnessAction.MIXED
            else Uniformity.MIXED
        ),
        red_green=(
            Uniformity.UNIFORM
            if global_actions.red_green_action is not RedGreenAction.MIXED
            else Uniformity.MIXED
        ),
        yellow_blue=(
            Uniformity.UNIFORM
            if global_actions.yellow_blue_action is not YellowBlueAction.MIXED
            else Uniformity.MIXED
        ),
    )
    flags = MultiangleCorrectionFlags(
        lightness_action_varies_by_angle=global_uniformity.lightness is Uniformity.MIXED,
        red_green_action_varies_by_angle=global_uniformity.red_green is Uniformity.MIXED,
        yellow_blue_action_varies_by_angle=global_uniformity.yellow_blue is Uniformity.MIXED,
    )
    worst = diagnosis.worst_angle
    worst_need = needs[worst]
    return ColorCorrectionNeed(
        session_id=comparison.session_id,
        target_measurement_id=comparison.target_measurement_id,
        sample_measurement_id=comparison.sample_measurement_id,
        target_guid=comparison.target_guid,
        sample_guid=comparison.sample_guid,
        by_angle=needs,
        front=_summary(
            needs, (MeasurementAngle.DEG_15, MeasurementAngle.DEG_25)
        ),
        mid=needs[MeasurementAngle.DEG_45],
        flop=_summary(
            needs, (MeasurementAngle.DEG_75, MeasurementAngle.DEG_105)
        ),
        global_actions=global_actions,
        global_uniformity=global_uniformity,
        worst_angle=worst,
        primary_issue=PrimaryIssue(
            angle=worst,
            group=_group_for_angle(worst),
            axis=worst_need.dominant_problem_axis,
            action=_primary_action(worst_need),
        ),
        multiangle_flags=flags,
    )
