from __future__ import annotations

import math
import os
import uuid

import pytest

from mandacor.application.comparison_service import compare_session
from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.correction import (
    LightnessAction,
    RedGreenAction,
    YellowBlueAction,
    derive_correction_need,
)
from mandacor.domain.diagnosis import (
    AxisSignPattern,
    DominantAxis,
    LightnessDirection,
    RedGreenDirection,
    YellowBlueDirection,
    diagnose_comparison,
)
from mandacor.domain.sessions import ColorSession, SessionState
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter


INSTRUMENT_IP = os.environ.get("MANDACOR_INSTRUMENT_IP")
SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")


def _manual_config() -> InstrumentConnectionConfig:
    if not INSTRUMENT_IP:
        pytest.skip("set MANDACOR_INSTRUMENT_IP for Gate 6 read-only test")
    return InstrumentConnectionConfig(
        mode=ConnectionMode.MANUAL,
        instrument_ip=INSTRUMENT_IP,
    )


@pytest.mark.instrument
def test_real_documented_target_12_sample_13_comparison_is_read_only():
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        target = adapter.get_measurement(12)
        sample = adapter.get_measurement(13)
        session = ColorSession.create(
            info.serial,
            uuid_factory=lambda: SESSION_ID,
        ).with_target(target).with_sample(sample)
        comparison = compare_session(session)
        diagnosis = diagnose_comparison(comparison)
        correction = derive_correction_need(diagnosis, comparison)
        assert session.state is SessionState.READY_FOR_COMPARISON
        assert comparison.session_id == SESSION_ID
        assert comparison.target_measurement_id == 12
        assert comparison.sample_measurement_id == 13
        assert tuple(comparison.angles) == tuple(MeasurementAngle)
        expected_diagnoses = {
            MeasurementAngle.DEG_15: (LightnessDirection.DARKER, RedGreenDirection.REDDER, YellowBlueDirection.BLUER, DominantAxis.L),
            MeasurementAngle.DEG_25: (LightnessDirection.DARKER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.L),
            MeasurementAngle.DEG_45: (LightnessDirection.DARKER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.B),
            MeasurementAngle.DEG_75: (LightnessDirection.LIGHTER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.B),
            MeasurementAngle.DEG_105: (LightnessDirection.LIGHTER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.B),
        }
        for current_angle, expected in expected_diagnoses.items():
            actual = diagnosis.angle_diagnoses[current_angle]
            assert (
                actual.lightness_direction,
                actual.red_green_direction,
                actual.yellow_blue_direction,
                actual.dominant_axis,
            ) == expected
        assert diagnosis.worst_angle is MeasurementAngle.DEG_15
        assert diagnosis.angles_by_delta_e_descending == tuple(MeasurementAngle)
        assert diagnosis.global_patterns.lightness is AxisSignPattern.SIGN_CROSSOVER
        assert diagnosis.global_patterns.red_green is AxisSignPattern.POSITIVE_ACROSS_ALL
        assert diagnosis.global_patterns.yellow_blue is AxisSignPattern.SIGN_CROSSOVER
        assert correction.front.lightness_action is LightnessAction.LIGHTEN
        assert correction.mid.lightness_action is LightnessAction.LIGHTEN
        assert correction.flop.lightness_action is LightnessAction.DARKEN
        assert correction.global_actions.red_green_action is RedGreenAction.MOVE_GREENER
        assert correction.front.yellow_blue_action is YellowBlueAction.MIXED
        assert correction.flop.yellow_blue_action is YellowBlueAction.MOVE_BLUER
        assert correction.primary_issue.action is LightnessAction.LIGHTEN
        assert session.target is target
        assert session.sample is sample
        assert session.state is SessionState.READY_FOR_COMPARISON

        angle = MeasurementAngle.DEG_15
        target_lab = target.angles[angle]
        sample_lab = sample.angles[angle]
        manual_l = sample_lab.L - target_lab.L
        manual_a = sample_lab.a - target_lab.a
        manual_b = sample_lab.b - target_lab.b
        manual_e = math.sqrt(
            manual_l * manual_l + manual_a * manual_a + manual_b * manual_b
        )
        engine = comparison.angles[angle]
        assert engine.delta_l == pytest.approx(manual_l)
        assert engine.delta_a == pytest.approx(manual_a)
        assert engine.delta_b == pytest.approx(manual_b)
        assert engine.delta_e76 == pytest.approx(manual_e)
        assert adapter.heartbeat_running

        for current_angle in MeasurementAngle:
            target_value = target.angles[current_angle]
            sample_value = sample.angles[current_angle]
            delta = comparison.angles[current_angle]
            print(
                {
                    "angle": int(current_angle),
                    "target": [target_value.L, target_value.a, target_value.b],
                    "sample": [sample_value.L, sample_value.a, sample_value.b],
                    "delta": [
                        delta.delta_l,
                        delta.delta_a,
                        delta.delta_b,
                        delta.delta_e76,
                    ],
                },
                flush=True,
            )
        print(
            {
                "independent_angle": 15,
                "manual": [manual_l, manual_a, manual_b, manual_e],
                "engine": [
                    engine.delta_l,
                    engine.delta_a,
                    engine.delta_b,
                    engine.delta_e76,
                ],
                "heartbeat_running": True,
                "worst_angle": int(diagnosis.worst_angle),
                "front": [
                    diagnosis.front_summary.lightness.value,
                    diagnosis.front_summary.red_green.value,
                    diagnosis.front_summary.yellow_blue.value,
                ],
                "flop": [
                    diagnosis.flop_summary.lightness.value,
                    diagnosis.flop_summary.red_green.value,
                    diagnosis.flop_summary.yellow_blue.value,
                ],
            },
            flush=True,
        )
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running
