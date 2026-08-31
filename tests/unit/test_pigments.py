from __future__ import annotations

import inspect
import math
import uuid
from dataclasses import FrozenInstanceError

import pytest

from mandacor.domain.comparison import AngleComparison, ColorComparison
from mandacor.domain.correction import derive_correction_need
from mandacor.domain.diagnosis import diagnose_comparison
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.pigments import (
    KNOWLEDGE_SCHEMA_VERSION,
    CandidateStatus,
    Confidence,
    ContraindicationSeverity,
    EffectDirection,
    EvidenceSource,
    FinishType,
    GENERAL_COLOR_RULES,
    GenericColorant,
    Opacity,
    PaintContext,
    PaintSystem,
    ParticleSize,
    PigmentContraindication,
    PigmentFamily,
    PigmentKnowledgeBase,
    PigmentProfile,
    PigmentRegionEffect,
    RiskTag,
    build_skylack_knowledge_base,
    evaluate_pigment_candidates,
)


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")
REAL_DELTAS = {
    MeasurementAngle.DEG_15: (-2.667785600000002, 0.11980533589999999, -0.07293820360000002),
    MeasurementAngle.DEG_25: (-1.5255966, 0.18647313110000002, 0.297808647),
    MeasurementAngle.DEG_45: (-0.25867840000000086, 0.19317865420000002, 0.4388928418),
    MeasurementAngle.DEG_75: (0.051396300000000394, 0.14901161227, 0.3870666025),
    MeasurementAngle.DEG_105: (0.11994270000000107, 0.1265108589, 0.3580033778),
}


def _correction(deltas):
    comparison = ColorComparison(
        SESSION_ID, 12, 13,
        {
            angle: AngleComparison(angle, dl, da, db, math.sqrt(dl**2 + da**2 + db**2))
            for angle, (dl, da, db) in deltas.items()
        },
    )
    return derive_correction_need(diagnose_comparison(comparison), comparison)


def _uniform(dl=0.0, da=0.0, db=0.0):
    return _correction({angle: (dl, da, db) for angle in MeasurementAngle})


def _profile(
    code="PX",
    *,
    front=PigmentRegionEffect(),
    mid=PigmentRegionEffect(),
    flop=PigmentRegionEffect(),
    name="Test pigment",
):
    return PigmentProfile(
        code=code,
        name=name,
        family=PigmentFamily.COLOR,
        paint_systems=frozenset({PaintSystem.UNKNOWN}),
        finish_compatibility=frozenset({FinishType.SOLID, FinishType.METALLIC, FinishType.PEARL}),
        front_effect=front,
        mid_effect=mid,
        flop_effect=flop,
        particle_size=ParticleSize.UNKNOWN,
        known_risks=frozenset(),
        contraindications=(),
        notes=(),
        evidence_source=EvidenceSource.VALIDATED_EXPERIMENT,
        confidence=Confidence.DOCUMENTED,
    )


def _kb(*profiles):
    return PigmentKnowledgeBase(KNOWLEDGE_SCHEMA_VERSION, "test", {p.code: p for p in profiles})


def _evaluate(correction, kb=None, finish=FinishType.SOLID):
    return evaluate_pigment_candidates(
        correction,
        PaintContext(PaintSystem.POLYESTER_BASECOAT, finish),
        kb or build_skylack_knowledge_base(),
    )


def _find(items, code):
    return next(item for item in items if item.pigment_code == code)


def test_all_required_pigment_codes_are_unique_and_registered():
    kb = build_skylack_knowledge_base()
    expected = {
        "AE650", "BP200", "BP203", "BP204", "BP205", "BP206", "BP207",
        "BP218", "BP219", "BP221", "BP225", "BP226", "BP231", "BP235",
        "BP248", "BP261", "BP262", "BP263", "BP264", "BP265", "BP266",
        "BP267", "BP268", "BP269", "BP270", "BP271", "BP282", "BP284",
        "BP285", "BP290", "BP299",
    }
    assert set(kb.profiles) == expected
    assert len(kb.profiles) == len(expected)


def test_all_profiles_validate_and_have_provenance_and_confidence():
    kb = build_skylack_knowledge_base()
    assert kb.knowledge_schema_version == 1
    assert all(profile.evidence_source in EvidenceSource for profile in kb.profiles.values())
    assert all(profile.confidence in Confidence for profile in kb.profiles.values())


def test_unknown_is_not_neutral():
    assert EffectDirection.UNKNOWN is not EffectDirection.NEUTRAL
    assert PigmentRegionEffect().lightness is EffectDirection.UNKNOWN


def test_general_color_rules_are_typed_but_do_not_override_specific_profiles():
    assert GENERAL_COLOR_RULES[GenericColorant.BLACK].lightness is EffectDirection.DARKEN
    assert GENERAL_COLOR_RULES[GenericColorant.WHITE].lightness is EffectDirection.LIGHTEN
    assert GENERAL_COLOR_RULES[GenericColorant.BLUE].yellow_blue is EffectDirection.MOVE_BLUER
    assert GENERAL_COLOR_RULES[GenericColorant.YELLOW].yellow_blue is EffectDirection.MOVE_YELLOWER
    assert GENERAL_COLOR_RULES[GenericColorant.RED].red_green is EffectDirection.MOVE_REDDER
    assert GENERAL_COLOR_RULES[GenericColorant.GREEN].red_green is EffectDirection.MOVE_GREENER
    assert GENERAL_COLOR_RULES[GenericColorant.VIOLET].yellow_blue is EffectDirection.MOVE_BLUER
    assert GENERAL_COLOR_RULES[GenericColorant.ORANGE].red_green is EffectDirection.MOVE_REDDER
    assert build_skylack_knowledge_base().get("BP200").front_effect.lightness is EffectDirection.UNKNOWN


def test_bp203_is_solid_lightener_and_hard_blocked_for_metallic_and_pearl():
    profile = build_skylack_knowledge_base().get("bp203")
    assert profile.family is PigmentFamily.WHITE
    assert profile.front_effect.lightness is EffectDirection.LIGHTEN
    assert profile.finish_compatibility == frozenset({FinishType.SOLID})
    for finish in (FinishType.METALLIC, FinishType.PEARL):
        result = _evaluate(_uniform(dl=-1), finish=finish)
        rejected = _find(result.rejected_candidates, "BP203")
        assert rejected.status is CandidateStatus.CONTRAINDICATED
        assert rejected.contraindications


def test_ae650_has_flop_opening_risk_and_is_not_plain_white():
    profile = build_skylack_knowledge_base().get("AE650")
    assert profile.family is not PigmentFamily.WHITE
    assert RiskTag.FLOP_OPENING in profile.known_risks
    assert profile.flop_effect.lightness is EffectDirection.LIGHTEN


def test_bp218_has_darkening_and_dirtying_risks():
    profile = build_skylack_knowledge_base().get("BP218")
    assert profile.family is PigmentFamily.BLACK
    assert {RiskTag.DARKENING, RiskTag.DIRTYING} <= profile.known_risks


def test_bp226_has_blue_green_coupled_effect():
    profile = build_skylack_knowledge_base().get("BP226")
    assert profile.front_effect.red_green is EffectDirection.MOVE_GREENER
    assert profile.front_effect.yellow_blue is EffectDirection.MOVE_BLUER
    assert RiskTag.HUE_COUPLING in profile.known_risks


def test_blue_pearls_preserve_documented_particle_difference():
    kb = build_skylack_knowledge_base()
    assert kb.get("BP282").particle_size is ParticleSize.FINE
    assert kb.get("BP284").particle_size is ParticleSize.COARSE
    assert kb.get("BP282").front_effect.yellow_blue is EffectDirection.MOVE_BLUER


def test_bp299_is_additive_and_not_a_color_candidate():
    profile = build_skylack_knowledge_base().get("BP299")
    assert profile.family is PigmentFamily.ADDITIVE
    assert not profile.eligible_as_color_candidate
    result = _evaluate(_uniform(da=1))
    assert _find(result.rejected_candidates, "BP299").status is CandidateStatus.CONTRAINDICATED


def test_bp261_through_bp271_are_unknown_without_sequence_inference():
    kb = build_skylack_knowledge_base()
    for number in range(261, 272):
        profile = kb.get(f"BP{number}")
        assert profile.family is PigmentFamily.ALUMINUM
        assert profile.particle_size is ParticleSize.UNKNOWN
        assert profile.front_effect == PigmentRegionEffect()
        assert profile.evidence_source is EvidenceSource.UNKNOWN
    assert kb.get("BP267").front_effect.lightness is EffectDirection.UNKNOWN


@pytest.mark.parametrize(
    ("delta", "effect"),
    [
        ((-1, 0, 0), PigmentRegionEffect(lightness=EffectDirection.LIGHTEN)),
        ((0, 1, 0), PigmentRegionEffect(red_green=EffectDirection.MOVE_GREENER)),
        ((0, 0, 1), PigmentRegionEffect(yellow_blue=EffectDirection.MOVE_BLUER)),
    ],
)
def test_candidate_matches_lighten_greener_and_bluer_needs(delta, effect):
    pigment = _profile(front=effect, mid=effect, flop=effect)
    candidate = _evaluate(_uniform(*delta), _kb(pigment)).candidates[0]
    assert candidate.status is CandidateStatus.RECOMMENDED_CANDIDATE
    assert len(candidate.matched_needs) == 5


def test_unknown_effect_is_neither_match_nor_neutral_and_name_has_no_fallback():
    pigment = _profile(name="Very blue pigment with no registered effect")
    result = _evaluate(_uniform(db=1), _kb(pigment))
    rejected = _find(result.rejected_candidates, "PX")
    assert rejected.status is CandidateStatus.INSUFFICIENT_KNOWLEDGE
    assert not rejected.matched_needs
    assert len(rejected.unknown_effects) == 5


def test_front_flop_conflict_is_reported_not_averaged():
    lighten = PigmentRegionEffect(lightness=EffectDirection.LIGHTEN)
    pigment = _profile(front=lighten, mid=lighten, flop=lighten)
    deltas = {
        MeasurementAngle.DEG_15: (-1, 0, 0),
        MeasurementAngle.DEG_25: (-1, 0, 0),
        MeasurementAngle.DEG_45: (-1, 0, 0),
        MeasurementAngle.DEG_75: (1, 0, 0),
        MeasurementAngle.DEG_105: (1, 0, 0),
    }
    candidate = _evaluate(_correction(deltas), _kb(pigment)).candidates[0]
    assert len(candidate.matched_needs) == 3
    assert [item.angle for item in candidate.conflicts] == [
        MeasurementAngle.DEG_75, MeasurementAngle.DEG_105
    ]
    assert candidate.status is CandidateStatus.CONDITIONAL


def test_uniform_move_greener_is_compatible_at_all_five_angles():
    effect = PigmentRegionEffect(red_green=EffectDirection.MOVE_GREENER)
    candidate = _evaluate(_uniform(da=1), _kb(_profile(front=effect, mid=effect, flop=effect))).candidates[0]
    assert len(candidate.matched_needs) == 5
    assert not candidate.conflicts


def test_coupled_pigment_can_match_b_and_conflict_a():
    effect = PigmentRegionEffect(
        red_green=EffectDirection.MOVE_GREENER,
        yellow_blue=EffectDirection.MOVE_BLUER,
    )
    candidate = _evaluate(_uniform(da=-1, db=1), _kb(_profile(front=effect, mid=effect, flop=effect))).candidates[0]
    assert {item.axis.value for item in candidate.matched_needs} == {"b"}
    assert {item.axis.value for item in candidate.conflicts} == {"a"}


def test_primary_issue_is_considered_by_status_rationale_and_ranking():
    primary = PigmentRegionEffect(lightness=EffectDirection.LIGHTEN)
    secondary = PigmentRegionEffect(red_green=EffectDirection.MOVE_GREENER)
    p1 = _profile("P1", front=primary, mid=primary, flop=primary)
    p2 = _profile("P2", front=secondary, mid=secondary, flop=secondary)
    result = _evaluate(_uniform(dl=-2, da=1), _kb(p2, p1))
    assert result.candidates[0].pigment_code == "P1"
    assert result.candidates[0].primary_issue_matched
    assert any("primary issue" in text for text in result.candidates[0].rationale)


def test_ranking_is_deterministic_with_code_as_final_tie_break():
    effect = PigmentRegionEffect(red_green=EffectDirection.MOVE_GREENER)
    profiles = [_profile(code, front=effect, mid=effect, flop=effect) for code in ("PZ", "PA", "PM")]
    first = _evaluate(_uniform(da=1), _kb(*profiles))
    second = _evaluate(_uniform(da=1), _kb(*reversed(profiles)))
    assert [item.pigment_code for item in first.candidates] == ["PA", "PM", "PZ"]
    assert first == second


def test_real_gate8_case_preserves_conflicts_and_allows_no_single_safe_candidate():
    result = _evaluate(_correction(REAL_DELTAS), finish=FinishType.METALLIC)
    assert result.primary_need.angle is MeasurementAngle.DEG_15
    assert result.no_single_safe_candidate
    assert result.requires_bench_test
    assert _find(result.rejected_candidates, "BP203").status is CandidateStatus.CONTRAINDICATED
    bp226 = _find(result.candidates, "BP226")
    assert bp226.matched_needs
    assert bp226.conflicts
    assert RiskTag.HUE_COUPLING in bp226.risks
    assert any("LIGHTNESS_CORRECTION_VARIES_WITH_ANGLE" in item for item in result.warnings)


def test_unknown_finish_emits_insufficient_context_and_relegates_white():
    result = _evaluate(_uniform(dl=-1), finish=FinishType.UNKNOWN)
    assert any("INSUFFICIENT_CONTEXT" in item for item in result.warnings)
    bp203 = _find(result.candidates, "BP203")
    assert bp203.status is CandidateStatus.CONDITIONAL
    assert bp203.contraindications


def test_recommendation_is_explainable_read_only_and_has_no_dosage_field():
    kb = build_skylack_knowledge_base()
    before = tuple(kb.profiles.items())
    result = _evaluate(_uniform(da=1), kb)
    assert all(item.rationale for item in result.candidates + result.rejected_candidates)
    assert tuple(kb.profiles.items()) == before
    with pytest.raises(TypeError):
        kb.profiles["NEW"] = kb.get("BP203")
    assert not hasattr(result, "grams")
    assert not hasattr(result, "dosage")
    with pytest.raises(FrozenInstanceError):
        result.requires_bench_test = False


def test_evaluator_has_no_random_score_ml_or_delta_e_selection():
    source = inspect.getsource(evaluate_pigment_candidates) + inspect.getsource(__import__("mandacor.domain.pigments", fromlist=["_rank_key"])._rank_key)
    lowered = source.lower()
    assert "random" not in lowered
    assert "score" not in lowered
    assert "delta_e" not in lowered
    assert "machine learning" not in lowered
