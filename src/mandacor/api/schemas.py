from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from mandacor.domain.adjustments import OperatorTrialStatus, VisualResult
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.pigments import FinishType, PaintSystem


class ConnectRequest(BaseModel):
    mode: str
    host: str | None = None

    @field_validator("mode")
    @classmethod
    def normalize_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"auto", "manual"}:
            raise ValueError("mode must be AUTO or MANUAL")
        return normalized


class WaitOperationRequest(BaseModel):
    timeout: float | None = Field(default=None, gt=0)
    poll_interval: float | None = Field(default=None, gt=0)


class PaintContextRequest(BaseModel):
    system: PaintSystem
    finish: FinishType

    @field_validator("system", "finish", mode="before")
    @classmethod
    def normalize_enum(cls, value):
        return value.lower() if isinstance(value, str) else value


class AdjustmentComponentRequest(BaseModel):
    pigment_code: str = Field(min_length=1)
    quantity_g: Decimal = Field(gt=0)


class AdjustmentCreateRequest(PaintContextRequest):
    volume_ml: Decimal = Field(gt=0)
    components: list[AdjustmentComponentRequest] = Field(min_length=1)
    operator_reason: str = Field(min_length=1)
    base_identifier: str | None = None
    color_description: str | None = None


class AbandonAdjustmentRequest(BaseModel):
    observation: str = Field(min_length=1)


class AdjustmentFeedbackRequest(BaseModel):
    visual_result: VisualResult
    operator_status: OperatorTrialStatus
    observations: str | None = None

    @field_validator("visual_result", "operator_status", mode="before")
    @classmethod
    def normalize_feedback_enum(cls, value):
        return value.lower() if isinstance(value, str) else value


def instrument_info_dict(info) -> dict[str, Any]:
    return {
        "manufacturer": info.manufacturer,
        "model": info.model,
        "serial": info.serial,
        "firmware": info.firmware,
        "ip": info.ip,
    }


def discovered_instrument_dict(item) -> dict[str, Any]:
    return {
        "manufacturer": item.manufacturer,
        "model": item.model,
        "serial": item.serial,
        "host": item.ip,
        "tcp_port": item.tcp_port,
        "udp_port": item.udp_port,
        "source": item.source,
    }


def measurement_reference_dict(reference) -> dict[str, Any]:
    return {
        "measurement_id": reference.measurement_id,
        "guid": reference.guid,
        "name": reference.name,
        "timestamp": reference.timestamp.isoformat() if reference.timestamp else None,
    }


def measurement_dict(measurement) -> dict[str, Any]:
    return {
        "measurement_id": measurement.measurement_id,
        "guid": measurement.guid,
        "timestamp": measurement.timestamp.isoformat() if measurement.timestamp else None,
        "timestamp_raw": measurement.timestamp_raw,
        "name": measurement.name,
        "instrument_serial": measurement.instrument_serial,
        "angles": [
            {
                "angle": int(angle),
                "l": measurement.angles[angle].L,
                "a": measurement.angles[angle].a,
                "b": measurement.angles[angle].b,
            }
            for angle in MeasurementAngle
        ],
    }


def session_dict(session) -> dict[str, Any]:
    return {
        "session_id": str(session.session_id),
        "state": session.state.name,
        "instrument_serial": session.instrument_serial,
        "target": measurement_dict(session.target) if session.target else None,
        "sample": measurement_dict(session.sample) if session.sample else None,
    }


def comparison_dict(comparison) -> dict[str, Any]:
    return {
        "convention": "SAMPLE_MINUS_TARGET",
        "target_id": comparison.target_measurement_id,
        "sample_id": comparison.sample_measurement_id,
        "angles": [
            {
                "angle": int(angle),
                "delta_l": comparison.angles[angle].delta_l,
                "delta_a": comparison.angles[angle].delta_a,
                "delta_b": comparison.angles[angle].delta_b,
                "delta_e76": comparison.angles[angle].delta_e76,
            }
            for angle in MeasurementAngle
        ],
    }


def diagnosis_dict(diagnosis) -> dict[str, Any]:
    return {
        "session_id": str(diagnosis.session_id),
        "worst_angle": int(diagnosis.worst_angle),
        "angles": [
            {
                "angle": int(angle),
                "lightness": diagnosis.angle_diagnoses[angle].lightness_direction.name,
                "red_green": diagnosis.angle_diagnoses[angle].red_green_direction.name,
                "yellow_blue": diagnosis.angle_diagnoses[angle].yellow_blue_direction.name,
                "dominant_axis": diagnosis.angle_diagnoses[angle].dominant_axis.name,
                "delta_e76": diagnosis.angle_diagnoses[angle].delta_e76,
            }
            for angle in MeasurementAngle
        ],
        "front": {
            "lightness": diagnosis.front_summary.lightness.name,
            "red_green": diagnosis.front_summary.red_green.name,
            "yellow_blue": diagnosis.front_summary.yellow_blue.name,
        },
        "mid": {
            "lightness": diagnosis.mid_angle_summary.lightness_direction.name,
            "red_green": diagnosis.mid_angle_summary.red_green_direction.name,
            "yellow_blue": diagnosis.mid_angle_summary.yellow_blue_direction.name,
        },
        "flop": {
            "lightness": diagnosis.flop_summary.lightness.name,
            "red_green": diagnosis.flop_summary.red_green.name,
            "yellow_blue": diagnosis.flop_summary.yellow_blue.name,
        },
    }


def correction_dict(correction) -> dict[str, Any]:
    def actions(item):
        return {
            "lightness": item.lightness_action.name,
            "red_green": item.red_green_action.name,
            "yellow_blue": item.yellow_blue_action.name,
        }

    return {
        "session_id": str(correction.session_id),
        "angles": [
            {
                "angle": int(angle),
                **actions(correction.by_angle[angle]),
                "correction_delta_l": correction.by_angle[angle].correction_delta_l,
                "correction_delta_a": correction.by_angle[angle].correction_delta_a,
                "correction_delta_b": correction.by_angle[angle].correction_delta_b,
            }
            for angle in MeasurementAngle
        ],
        "front": actions(correction.front),
        "mid": actions(correction.mid),
        "flop": actions(correction.flop),
        "global_actions": actions(correction.global_actions),
        "global_uniformity": {
            "lightness": correction.global_uniformity.lightness.name,
            "red_green": correction.global_uniformity.red_green.name,
            "yellow_blue": correction.global_uniformity.yellow_blue.name,
        },
        "primary_issue": {
            "angle": int(correction.primary_issue.angle),
            "group": correction.primary_issue.group.name,
            "axis": correction.primary_issue.axis.name,
            "action": correction.primary_issue.action.name if correction.primary_issue.action else None,
        },
    }


def pigment_recommendation_dict(recommendation) -> dict[str, Any]:
    def assessment(item):
        return {
            "angle": int(item.angle),
            "group": item.group.name,
            "axis": item.axis.name,
            "need": item.need.name,
            "pigment_effect": item.pigment_effect.name,
        }

    def candidate(item):
        return {
            "pigment_code": item.pigment_code,
            "status": item.status.name,
            "matched_needs": [assessment(value) for value in item.matched_needs],
            "conflicts": [assessment(value) for value in item.conflicts],
            "unknown_effects": [assessment(value) for value in item.unknown_effects],
            "risks": [value.name for value in item.risks],
            "contraindications": list(item.contraindications),
            "rationale": list(item.rationale),
        }

    return {
        "candidates": [candidate(item) for item in recommendation.candidates],
        "rejected_candidates": [candidate(item) for item in recommendation.rejected_candidates],
        "warnings": list(recommendation.warnings),
        "requires_bench_test": recommendation.requires_bench_test,
        "no_single_safe_candidate": recommendation.no_single_safe_candidate,
        "dosage_available": False,
    }


def adjustment_dict(adjustment) -> dict[str, Any]:
    result = {
        "adjustment_id": str(adjustment.adjustment_id),
        "session_id": str(adjustment.session_id),
        "lifecycle": adjustment.lifecycle.name,
        "target_measurement_id": adjustment.target.measurement_id,
        "before_measurement_id": adjustment.before.measurement_id,
        "after_measurement_id": getattr(getattr(adjustment, "after", None), "measurement_id", None),
        "system": adjustment.paint_context.system.name,
        "finish": adjustment.paint_context.finish_type.name,
        "volume_ml": format(adjustment.volume_ml, "f"),
        "components": [
            {"pigment_code": item.pigment_code, "quantity_g": format(item.quantity_g, "f")}
            for item in adjustment.components
        ],
        "operator_reason": adjustment.operator_reason,
        "target": measurement_dict(adjustment.target),
        "before": measurement_dict(adjustment.before),
        "after": measurement_dict(adjustment.after) if hasattr(adjustment, "after") else None,
        "created_at": adjustment.created_at.isoformat(),
        "applied_at": adjustment.applied_at.isoformat() if adjustment.applied_at else None,
        "completed_at": (
            adjustment.completed_at.isoformat() if hasattr(adjustment, "completed_at") else None
        ),
        "observations": adjustment.observations,
        "base_identifier": adjustment.base_identifier,
        "color_description": adjustment.color_description,
        "learning_eligibility": adjustment.learning_eligibility.name,
        "dosage_generated_by_system": False,
    }
    if hasattr(adjustment, "observed_response_by_angle"):
        result.update(
            {
                "observed_response": [
                    {
                        "angle": int(angle),
                        "response_l": adjustment.observed_response_by_angle[angle].response_l,
                        "response_a": adjustment.observed_response_by_angle[angle].response_a,
                        "response_b": adjustment.observed_response_by_angle[angle].response_b,
                    }
                    for angle in MeasurementAngle
                ],
                "before_comparison": comparison_dict(adjustment.before_comparison),
                "after_comparison": comparison_dict(adjustment.after_comparison),
                "outcomes": [
                    {
                        "angle": int(angle),
                        "before_delta_e76": adjustment.outcome_by_angle[angle].before_delta_e76,
                        "after_delta_e76": adjustment.outcome_by_angle[angle].after_delta_e76,
                        "delta_e_improvement": adjustment.outcome_by_angle[angle].delta_e_improvement,
                        "improvement_l": adjustment.outcome_by_angle[angle].improvement_l,
                        "lightness_outcome": adjustment.outcome_by_angle[angle].lightness_outcome.name,
                        "improvement_a": adjustment.outcome_by_angle[angle].improvement_a,
                        "red_green_outcome": adjustment.outcome_by_angle[angle].red_green_outcome.name,
                        "improvement_b": adjustment.outcome_by_angle[angle].improvement_b,
                        "yellow_blue_outcome": adjustment.outcome_by_angle[angle].yellow_blue_outcome.name,
                        "delta_e_outcome": adjustment.outcome_by_angle[angle].delta_e_outcome.name,
                    }
                    for angle in MeasurementAngle
                ],
                "worst_angle_before": int(adjustment.worst_angle_before),
                "worst_angle_after": int(adjustment.worst_angle_after),
                "visual_result": adjustment.visual_result.name,
                "operator_status": adjustment.operator_status.name,
                "data_quality_flags": sorted(flag.name for flag in adjustment.data_quality_flags),
            }
        )
    else:
        result.update(
            {
                "observed_response": None,
                "before_comparison": None,
                "after_comparison": None,
                "outcomes": None,
                "worst_angle_before": None,
                "worst_angle_after": None,
                "visual_result": None,
                "operator_status": None,
                "data_quality_flags": None,
            }
        )
    return result
