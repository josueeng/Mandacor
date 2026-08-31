from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from mandacor.domain.correction import (
    AngleGroup,
    ColorCorrectionNeed,
    LightnessAction,
    PrimaryIssue,
    RedGreenAction,
    YellowBlueAction,
)
from mandacor.domain.diagnosis import DominantAxis
from mandacor.domain.measurements import MeasurementAngle


KNOWLEDGE_SCHEMA_VERSION = 1
KNOWLEDGE_REVISION = "gate-9-initial"


class PaintSystem(str, Enum):
    POLYESTER_BASECOAT = "polyester_basecoat"
    PU = "pu"
    UNKNOWN = "unknown"


class FinishType(str, Enum):
    SOLID = "solid"
    METALLIC = "metallic"
    PEARL = "pearl"
    UNKNOWN = "unknown"


class PigmentFamily(str, Enum):
    COLOR = "color"
    WHITE = "white"
    BLACK = "black"
    ALUMINUM = "aluminum"
    PEARL = "pearl"
    ADDITIVE = "additive"
    OTHER = "other"


class EvidenceSource(str, Enum):
    MANUFACTURER_MANUAL = "manufacturer_manual"
    SHOP_EMPIRICAL = "shop_empirical"
    VALIDATED_EXPERIMENT = "validated_experiment"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    DOCUMENTED = "documented"
    EMPIRICAL = "empirical"
    UNKNOWN = "unknown"


class EffectDirection(str, Enum):
    UNKNOWN = "unknown"
    NEUTRAL = "neutral"
    LIGHTEN = "lighten"
    DARKEN = "darken"
    MOVE_REDDER = "move_redder"
    MOVE_GREENER = "move_greener"
    MOVE_YELLOWER = "move_yellower"
    MOVE_BLUER = "move_bluer"


class Opacity(str, Enum):
    OPAQUE = "opaque"
    TRANSPARENT = "transparent"
    UNKNOWN = "unknown"


class ParticleSize(str, Enum):
    FINE = "fine"
    MEDIUM = "medium"
    COARSE = "coarse"
    UNKNOWN = "unknown"


class RiskTag(str, Enum):
    MILKY = "milky"
    DIRTYING = "dirtying"
    DARKENING = "darkening"
    STRONG_DARKENING = "strong_darkening"
    LIGHTENING = "lightening"
    FLOP_OPENING = "flop_opening"
    FRONT_DIRTYING = "front_dirtying"
    PARTICLE_CHANGE = "particle_change"
    HUE_COUPLING = "hue_coupling"
    EFFECT_CHANGE = "effect_change"


class ContraindicationSeverity(str, Enum):
    HARD = "hard"
    WARNING = "warning"


class ColorAxis(str, Enum):
    L = "l"
    A = "a"
    B = "b"


class CandidateStatus(str, Enum):
    RECOMMENDED_CANDIDATE = "recommended_candidate"
    CONDITIONAL = "conditional"
    CONFLICTING = "conflicting"
    CONTRAINDICATED = "contraindicated"
    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"


class GenericColorant(str, Enum):
    BLACK = "black"
    WHITE = "white"
    BLUE = "blue"
    YELLOW = "yellow"
    RED = "red"
    GREEN = "green"
    VIOLET = "violet"
    ORANGE = "orange"


@dataclass(frozen=True, slots=True)
class PaintContext:
    system: PaintSystem
    finish_type: FinishType


@dataclass(frozen=True, slots=True)
class PigmentRegionEffect:
    lightness: EffectDirection = EffectDirection.UNKNOWN
    red_green: EffectDirection = EffectDirection.UNKNOWN
    yellow_blue: EffectDirection = EffectDirection.UNKNOWN
    opacity: Opacity = Opacity.UNKNOWN
    notes: tuple[str, ...] = ()


UNKNOWN_EFFECT = PigmentRegionEffect()

GENERAL_COLOR_RULES: Mapping[GenericColorant, PigmentRegionEffect] = MappingProxyType({
    GenericColorant.BLACK: PigmentRegionEffect(lightness=EffectDirection.DARKEN),
    GenericColorant.WHITE: PigmentRegionEffect(lightness=EffectDirection.LIGHTEN),
    GenericColorant.BLUE: PigmentRegionEffect(yellow_blue=EffectDirection.MOVE_BLUER),
    GenericColorant.YELLOW: PigmentRegionEffect(yellow_blue=EffectDirection.MOVE_YELLOWER),
    GenericColorant.RED: PigmentRegionEffect(red_green=EffectDirection.MOVE_REDDER),
    GenericColorant.GREEN: PigmentRegionEffect(red_green=EffectDirection.MOVE_GREENER),
    GenericColorant.VIOLET: PigmentRegionEffect(yellow_blue=EffectDirection.MOVE_BLUER),
    GenericColorant.ORANGE: PigmentRegionEffect(red_green=EffectDirection.MOVE_REDDER),
})


@dataclass(frozen=True, slots=True)
class PigmentContraindication:
    finish_types: frozenset[FinishType]
    severity: ContraindicationSeverity
    reason: str


@dataclass(frozen=True, slots=True)
class PigmentProfile:
    code: str
    name: str
    family: PigmentFamily
    paint_systems: frozenset[PaintSystem]
    finish_compatibility: frozenset[FinishType]
    front_effect: PigmentRegionEffect
    mid_effect: PigmentRegionEffect
    flop_effect: PigmentRegionEffect
    particle_size: ParticleSize
    known_risks: frozenset[RiskTag]
    contraindications: tuple[PigmentContraindication, ...]
    notes: tuple[str, ...]
    evidence_source: EvidenceSource
    confidence: Confidence
    eligible_as_color_candidate: bool = True

    def __post_init__(self) -> None:
        normalized = self.code.strip().upper()
        if not normalized:
            raise ValueError("pigment code cannot be empty")
        object.__setattr__(self, "code", normalized)
        if not self.name.strip():
            raise ValueError(f"pigment {normalized} must have a name")
        if not isinstance(self.family, PigmentFamily):
            raise ValueError(f"pigment {normalized} has invalid family")
        if not self.paint_systems or not all(
            isinstance(item, PaintSystem) for item in self.paint_systems
        ):
            raise ValueError(f"pigment {normalized} must declare paint systems")
        if not self.finish_compatibility or not all(
            isinstance(item, FinishType) for item in self.finish_compatibility
        ):
            raise ValueError(f"pigment {normalized} must declare finish compatibility")
        if not all(
            isinstance(effect, PigmentRegionEffect)
            for effect in (self.front_effect, self.mid_effect, self.flop_effect)
        ):
            raise ValueError(f"pigment {normalized} has invalid regional effect")
        if not isinstance(self.evidence_source, EvidenceSource) or not isinstance(
            self.confidence, Confidence
        ):
            raise ValueError(f"pigment {normalized} must declare valid provenance")

    def effect_for_angle(self, angle: MeasurementAngle) -> PigmentRegionEffect:
        if angle in (MeasurementAngle.DEG_15, MeasurementAngle.DEG_25):
            return self.front_effect
        if angle is MeasurementAngle.DEG_45:
            return self.mid_effect
        return self.flop_effect


@dataclass(frozen=True, slots=True)
class PigmentKnowledgeBase:
    knowledge_schema_version: int
    knowledge_revision: str
    profiles: Mapping[str, PigmentProfile]

    def __post_init__(self) -> None:
        if self.knowledge_schema_version != KNOWLEDGE_SCHEMA_VERSION:
            raise ValueError("unsupported pigment knowledge schema version")
        normalized: dict[str, PigmentProfile] = {}
        for key, profile in self.profiles.items():
            code = key.strip().upper()
            if code != profile.code:
                raise ValueError("knowledge key must match pigment code")
            if code in normalized:
                raise ValueError(f"duplicate pigment code: {code}")
            normalized[code] = profile
        object.__setattr__(self, "profiles", MappingProxyType(normalized))

    def get(self, code: str) -> PigmentProfile:
        return self.profiles[code.strip().upper()]


@dataclass(frozen=True, slots=True)
class NeedAssessment:
    angle: MeasurementAngle
    group: AngleGroup
    axis: ColorAxis
    need: EffectDirection
    pigment_effect: EffectDirection


@dataclass(frozen=True, slots=True)
class PigmentCandidate:
    pigment_code: str
    status: CandidateStatus
    matched_needs: tuple[NeedAssessment, ...]
    conflicts: tuple[NeedAssessment, ...]
    unknown_effects: tuple[NeedAssessment, ...]
    risks: tuple[RiskTag, ...]
    contraindications: tuple[str, ...]
    rationale: tuple[str, ...]
    primary_issue_matched: bool
    primary_issue_conflicted: bool


@dataclass(frozen=True, slots=True)
class QualitativePigmentRecommendation:
    context: PaintContext
    primary_need: PrimaryIssue
    candidates: tuple[PigmentCandidate, ...]
    rejected_candidates: tuple[PigmentCandidate, ...]
    warnings: tuple[str, ...]
    requires_bench_test: bool
    no_single_safe_candidate: bool


def _effect(
    *,
    lightness: EffectDirection = EffectDirection.UNKNOWN,
    red_green: EffectDirection = EffectDirection.UNKNOWN,
    yellow_blue: EffectDirection = EffectDirection.UNKNOWN,
    opacity: Opacity = Opacity.UNKNOWN,
    notes: tuple[str, ...] = (),
) -> PigmentRegionEffect:
    return PigmentRegionEffect(lightness, red_green, yellow_blue, opacity, notes)


def _profile(
    code: str,
    name: str,
    family: PigmentFamily,
    *,
    front: PigmentRegionEffect = UNKNOWN_EFFECT,
    mid: PigmentRegionEffect = UNKNOWN_EFFECT,
    flop: PigmentRegionEffect = UNKNOWN_EFFECT,
    particle: ParticleSize = ParticleSize.UNKNOWN,
    risks: frozenset[RiskTag] = frozenset(),
    contraindications: tuple[PigmentContraindication, ...] = (),
    notes: tuple[str, ...] = (),
    source: EvidenceSource = EvidenceSource.SHOP_EMPIRICAL,
    confidence: Confidence = Confidence.EMPIRICAL,
    systems: frozenset[PaintSystem] = frozenset({PaintSystem.UNKNOWN}),
    finishes: frozenset[FinishType] = frozenset(
        {FinishType.SOLID, FinishType.METALLIC, FinishType.PEARL, FinishType.UNKNOWN}
    ),
    eligible: bool = True,
) -> PigmentProfile:
    return PigmentProfile(
        code, name, family, systems, finishes, front, mid, flop, particle,
        risks, contraindications, notes, source, confidence, eligible,
    )


def build_skylack_knowledge_base() -> PigmentKnowledgeBase:
    all_regions_lighten = _effect(lightness=EffectDirection.LIGHTEN)
    all_regions_darken = _effect(lightness=EffectDirection.DARKEN)
    profiles = [
        _profile(
            "AE650", "Effect opener", PigmentFamily.OTHER,
            mid=all_regions_lighten,
            flop=all_regions_lighten,
            risks=frozenset({RiskTag.EFFECT_CHANGE, RiskTag.FLOP_OPENING}),
            notes=("Opens/lightens viewing angle and increases aluminum/pearl appearance.",),
        ),
        _profile(
            "BP200", "White", PigmentFamily.WHITE,
            risks=frozenset({RiskTag.MILKY, RiskTag.FRONT_DIRTYING}),
            notes=("Can make the angle milky and dirty the front; not a universal lightener.",),
        ),
        _profile(
            "BP203", "Base white", PigmentFamily.WHITE,
            front=all_regions_lighten, mid=all_regions_lighten, flop=all_regions_lighten,
            finishes=frozenset({FinishType.SOLID}),
            contraindications=(PigmentContraindication(
                frozenset({FinishType.METALLIC, FinishType.PEARL}),
                ContraindicationSeverity.HARD,
                "Solid-color white is contraindicated as a lightener for metallic or pearl finishes.",
            ),),
            notes=("Lightens solid colors.",),
        ),
        _profile(
            "BP204", "Red-shade violet blue", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.DIRTYING, RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP205", "Angle-shift blue", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(red_green=EffectDirection.MOVE_REDDER),
            risks=frozenset({RiskTag.HUE_COUPLING}),
            notes=("Green-shade blue at front; slightly redder at flop.",),
        ),
        _profile(
            "BP206", "Dark blue", PigmentFamily.COLOR,
            front=_effect(lightness=EffectDirection.DARKEN, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(lightness=EffectDirection.DARKEN, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(lightness=EffectDirection.DARKEN, red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.DARKENING, RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP207", "Green", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP218", "Black", PigmentFamily.BLACK,
            front=all_regions_darken, mid=all_regions_darken, flop=all_regions_darken,
            risks=frozenset({RiskTag.DARKENING, RiskTag.DIRTYING, RiskTag.FRONT_DIRTYING}),
            notes=("Darkens and can dirty both front and angle.",),
        ),
        _profile(
            "BP219", "Micronized white", PigmentFamily.WHITE,
            front=all_regions_lighten, mid=all_regions_lighten, flop=all_regions_lighten,
            risks=frozenset({RiskTag.MILKY, RiskTag.HUE_COUPLING}),
            notes=("Light/milky angle; blue/gold behavior is documented but not region-resolved.",),
        ),
        _profile(
            "BP221", "Clean red-shade dark blue", PigmentFamily.COLOR,
            front=_effect(lightness=EffectDirection.DARKEN, red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(lightness=EffectDirection.DARKEN, red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(lightness=EffectDirection.DARKEN, red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.DARKENING, RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP225", "Blue violet", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP226", "Clean green-shade blue", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(red_green=EffectDirection.MOVE_GREENER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP231", "Blue-shade ruby red", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(lightness=EffectDirection.LIGHTEN, red_green=EffectDirection.MOVE_REDDER, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.HUE_COUPLING, RiskTag.LIGHTENING}),
        ),
        _profile(
            "BP235", "Strong transparent clean red", PigmentFamily.COLOR,
            front=_effect(red_green=EffectDirection.MOVE_REDDER, opacity=Opacity.TRANSPARENT),
            mid=_effect(red_green=EffectDirection.MOVE_REDDER, opacity=Opacity.TRANSPARENT),
            flop=_effect(red_green=EffectDirection.MOVE_REDDER, opacity=Opacity.TRANSPARENT),
        ),
        _profile(
            "BP248", "Intense black", PigmentFamily.BLACK,
            front=all_regions_darken, mid=all_regions_darken, flop=all_regions_darken,
            risks=frozenset({RiskTag.DARKENING, RiskTag.STRONG_DARKENING}),
        ),
    ]
    for code in ("BP261", "BP262", "BP263", "BP264", "BP265", "BP266", "BP267", "BP268", "BP269", "BP270", "BP271"):
        profiles.append(_profile(
            code, "Aluminum — effect unknown", PigmentFamily.ALUMINUM,
            particle=ParticleSize.UNKNOWN,
            risks=frozenset({RiskTag.PARTICLE_CHANGE, RiskTag.EFFECT_CHANGE}),
            notes=("Individual behavior is not confirmed; no inference is made from code sequence.",),
            source=EvidenceSource.UNKNOWN,
            confidence=Confidence.UNKNOWN,
        ))
    profiles.extend([
        _profile(
            "BP282", "Fine blue pearl", PigmentFamily.PEARL,
            front=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            particle=ParticleSize.FINE,
            risks=frozenset({RiskTag.PARTICLE_CHANGE, RiskTag.EFFECT_CHANGE, RiskTag.HUE_COUPLING}),
        ),
        _profile(
            "BP284", "Coarse blue pearl", PigmentFamily.PEARL,
            front=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            particle=ParticleSize.COARSE,
            risks=frozenset({RiskTag.PARTICLE_CHANGE, RiskTag.EFFECT_CHANGE, RiskTag.HUE_COUPLING}),
            notes=("Coarser than BP282 and documented as lighter at front.",),
        ),
        _profile(
            "BP285", "Bright silver pearl", PigmentFamily.PEARL,
            front=all_regions_lighten, mid=all_regions_lighten, flop=all_regions_lighten,
            risks=frozenset({RiskTag.PARTICLE_CHANGE, RiskTag.EFFECT_CHANGE, RiskTag.LIGHTENING}),
        ),
        _profile(
            "BP290", "Blue-violet pearl", PigmentFamily.PEARL,
            front=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            mid=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            flop=_effect(lightness=EffectDirection.LIGHTEN, yellow_blue=EffectDirection.MOVE_BLUER),
            risks=frozenset({RiskTag.PARTICLE_CHANGE, RiskTag.EFFECT_CHANGE, RiskTag.HUE_COUPLING}),
            notes=("Violet/blue tendency is retained without inventing a separate red-axis effect.",),
        ),
        _profile(
            "BP299", "Polyester basecoat additive", PigmentFamily.ADDITIVE,
            systems=frozenset({PaintSystem.POLYESTER_BASECOAT}),
            eligible=False,
            notes=("Not eligible as a direct chromatic correction without a specific rule.",),
        ),
    ])
    return PigmentKnowledgeBase(
        KNOWLEDGE_SCHEMA_VERSION,
        KNOWLEDGE_REVISION,
        {profile.code: profile for profile in profiles},
    )


def _group(angle: MeasurementAngle) -> AngleGroup:
    if angle in (MeasurementAngle.DEG_15, MeasurementAngle.DEG_25):
        return AngleGroup.FRONT
    if angle is MeasurementAngle.DEG_45:
        return AngleGroup.MID
    return AngleGroup.FLOP


def _needed_effect(action: object) -> EffectDirection | None:
    mapping = {
        LightnessAction.LIGHTEN: EffectDirection.LIGHTEN,
        LightnessAction.DARKEN: EffectDirection.DARKEN,
        RedGreenAction.MOVE_REDDER: EffectDirection.MOVE_REDDER,
        RedGreenAction.MOVE_GREENER: EffectDirection.MOVE_GREENER,
        YellowBlueAction.MOVE_YELLOWER: EffectDirection.MOVE_YELLOWER,
        YellowBlueAction.MOVE_BLUER: EffectDirection.MOVE_BLUER,
    }
    return mapping.get(action)


def _opposite(effect: EffectDirection) -> EffectDirection | None:
    return {
        EffectDirection.LIGHTEN: EffectDirection.DARKEN,
        EffectDirection.DARKEN: EffectDirection.LIGHTEN,
        EffectDirection.MOVE_REDDER: EffectDirection.MOVE_GREENER,
        EffectDirection.MOVE_GREENER: EffectDirection.MOVE_REDDER,
        EffectDirection.MOVE_YELLOWER: EffectDirection.MOVE_BLUER,
        EffectDirection.MOVE_BLUER: EffectDirection.MOVE_YELLOWER,
    }.get(effect)


def _effect_on_axis(effect: PigmentRegionEffect, axis: ColorAxis) -> EffectDirection:
    if axis is ColorAxis.L:
        return effect.lightness
    if axis is ColorAxis.A:
        return effect.red_green
    return effect.yellow_blue


def _candidate(
    profile: PigmentProfile,
    correction: ColorCorrectionNeed,
    context: PaintContext,
) -> PigmentCandidate:
    hard_reasons = tuple(
        item.reason
        for item in profile.contraindications
        if item.severity is ContraindicationSeverity.HARD
        and context.finish_type in item.finish_types
    )
    warning_reasons = tuple(
        item.reason
        for item in profile.contraindications
        if item.severity is ContraindicationSeverity.WARNING
        and context.finish_type in item.finish_types
    )
    if (
        context.finish_type is FinishType.UNKNOWN
        and profile.family in {PigmentFamily.WHITE, PigmentFamily.ALUMINUM, PigmentFamily.PEARL}
    ):
        warning_reasons += ("Finish type is unknown; white/effect compatibility cannot be confirmed.",)
    if not profile.eligible_as_color_candidate:
        hard_reasons += ("Profile is not eligible as a direct color candidate.",)

    matched: list[NeedAssessment] = []
    conflicts: list[NeedAssessment] = []
    unknowns: list[NeedAssessment] = []
    primary_match = False
    primary_conflict = False
    for angle, need in correction.by_angle.items():
        effect = profile.effect_for_angle(angle)
        for axis, action in (
            (ColorAxis.L, need.lightness_action),
            (ColorAxis.A, need.red_green_action),
            (ColorAxis.B, need.yellow_blue_action),
        ):
            wanted = _needed_effect(action)
            if wanted is None:
                continue
            actual = _effect_on_axis(effect, axis)
            assessment = NeedAssessment(angle, _group(angle), axis, wanted, actual)
            is_primary = (
                angle is correction.primary_issue.angle
                and axis.value == correction.primary_issue.axis.value
            )
            if actual is EffectDirection.UNKNOWN:
                unknowns.append(assessment)
            elif actual is wanted:
                matched.append(assessment)
                primary_match = primary_match or is_primary
            elif actual is _opposite(wanted):
                conflicts.append(assessment)
                primary_conflict = primary_conflict or is_primary

    if hard_reasons:
        status = CandidateStatus.CONTRAINDICATED
    elif not matched:
        status = (
            CandidateStatus.CONFLICTING
            if conflicts
            else CandidateStatus.INSUFFICIENT_KNOWLEDGE
        )
    elif primary_match and not conflicts and not warning_reasons and not profile.known_risks:
        status = CandidateStatus.RECOMMENDED_CANDIDATE
    else:
        status = CandidateStatus.CONDITIONAL
    rationale = []
    if matched:
        rationale.append(f"Matches {len(matched)} angle-axis correction need(s).")
    if primary_match:
        rationale.append("Matches the primary issue inherited from Gate 8.")
    if conflicts:
        rationale.append(f"Conflicts with {len(conflicts)} angle-axis need(s).")
    if unknowns:
        rationale.append(f"Has unknown effect for {len(unknowns)} required angle-axis item(s).")
    if hard_reasons:
        rationale.append("Rejected by a hard context contraindication.")
    if not rationale:
        rationale.append("No documented compatible effect was found.")
    return PigmentCandidate(
        profile.code,
        status,
        tuple(matched),
        tuple(conflicts),
        tuple(unknowns),
        tuple(sorted(profile.known_risks, key=lambda item: item.value)),
        hard_reasons + warning_reasons,
        tuple(rationale),
        primary_match,
        primary_conflict,
    )


def _rank_key(candidate: PigmentCandidate) -> tuple[object, ...]:
    return (
        candidate.primary_issue_conflicted,
        not candidate.primary_issue_matched,
        -len(candidate.matched_needs),
        len(candidate.conflicts),
        len(candidate.unknown_effects),
        candidate.pigment_code,
    )


def evaluate_pigment_candidates(
    correction_need: ColorCorrectionNeed,
    paint_context: PaintContext,
    knowledge_base: PigmentKnowledgeBase,
) -> QualitativePigmentRecommendation:
    evaluated = [
        _candidate(profile, correction_need, paint_context)
        for profile in knowledge_base.profiles.values()
    ]
    rejected_statuses = {
        CandidateStatus.CONTRAINDICATED,
        CandidateStatus.INSUFFICIENT_KNOWLEDGE,
    }
    candidates = tuple(sorted(
        (item for item in evaluated if item.status not in rejected_statuses),
        key=_rank_key,
    ))
    rejected = tuple(sorted(
        (item for item in evaluated if item.status in rejected_statuses),
        key=lambda item: item.pigment_code,
    ))
    safe = any(
        item.primary_issue_matched and not item.conflicts
        and item.status is CandidateStatus.RECOMMENDED_CANDIDATE
        for item in candidates
    )
    warnings: list[str] = []
    if paint_context.finish_type is FinishType.UNKNOWN:
        warnings.append("INSUFFICIENT_CONTEXT: finish type is required for safe white/effect selection.")
    flags = correction_need.multiangle_flags
    if flags.lightness_action_varies_by_angle:
        warnings.append("LIGHTNESS_CORRECTION_VARIES_WITH_ANGLE.")
    if flags.red_green_action_varies_by_angle:
        warnings.append("RED_GREEN_ACTION_VARIES_BY_ANGLE.")
    if flags.yellow_blue_action_varies_by_angle:
        warnings.append("YELLOW_BLUE_ACTION_VARIES_BY_ANGLE.")
    if not safe:
        warnings.append("NO_SINGLE_SAFE_CANDIDATE: multiangle conflict requires a bench test.")
    warnings.append("No dosage has been calculated; bench test before physical adjustment.")
    return QualitativePigmentRecommendation(
        paint_context,
        correction_need.primary_issue,
        candidates,
        rejected,
        tuple(warnings),
        requires_bench_test=True,
        no_single_safe_candidate=not safe,
    )
