from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from mandacor.application.comparison_service import compare_session
from mandacor.application.adjustment_dataset import AdjustmentDatasetExporter
from mandacor.application.adjustment_workflow import AdjustmentWorkflow
from mandacor.application.instrument_service import InstrumentService
from mandacor.application.measurement_wait import (
    MeasurementWaitCancelledError,
    NewMeasurementTimeoutError,
)
from mandacor.application.sample_capture import CaptureSampleService
from mandacor.application.target_capture import CaptureTargetService
from mandacor.config import ConnectionMode
from mandacor.config import ApiConfig
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.adjustments import (
    AdjustmentComponent,
    AdjustmentHistory,
    AdjustmentLifecycle,
    OperatorTrialStatus,
    VisualResult,
    plan_adjustment,
)
from mandacor.domain.correction import derive_correction_need
from mandacor.domain.diagnosis import diagnose_comparison
from mandacor.domain.pigments import (
    FinishType,
    PaintContext,
    PaintSystem,
    build_skylack_knowledge_base,
    evaluate_pigment_candidates,
)
from mandacor.domain.sessions import ColorSession
from mandacor.infrastructure.config.json_config import JsonConfigurationRepository
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentError
from mandacor.infrastructure.storage.pending_adjustment_json import (
    JsonPendingAdjustmentRepository,
)


def _component_argument(value: str) -> AdjustmentComponent:
    code, separator, quantity = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("component must use CODE=QUANTITY_G")
    try:
        return AdjustmentComponent(code, quantity)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mandacor")
    parser.add_argument("--config", default="config/mandacor.json")
    commands = parser.add_subparsers(dest="group", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--pending-file", default="data/pending_adjustment.json")
    doctor.add_argument("--data-dir", default="data")
    dataset = commands.add_parser("dataset")
    dataset_actions = dataset.add_subparsers(dest="action", required=True)
    formula_export = dataset_actions.add_parser("export-formula-training")
    formula_export.add_argument("--catalog", default="data/formulas.sqlite3")
    formula_export.add_argument("--output", default="data/ml/formula_spectra.jsonl")
    formula_export.add_argument("--include-review", action="store_true")
    instrument = commands.add_parser("instrument")
    actions = instrument.add_subparsers(dest="action", required=True)
    actions.add_parser("discover")
    connect = actions.add_parser("connect")
    connect.add_argument("--ip")
    actions.add_parser("info")
    config = actions.add_parser("config")
    config.add_argument("--mode", choices=[mode.value for mode in ConnectionMode])
    config.add_argument("--ip")
    config.add_argument("--discovery-address")
    config.add_argument("--local-interface")
    measurement = commands.add_parser("measurement")
    measurement_actions = measurement.add_subparsers(dest="action", required=True)
    measurement_list = measurement_actions.add_parser("list")
    measurement_list.add_argument("--ip")
    measurement_get = measurement_actions.add_parser("get")
    measurement_get.add_argument("measurement_id", type=int)
    measurement_get.add_argument("--ip")
    measurement_latest = measurement_actions.add_parser("latest")
    measurement_latest.add_argument("--ip")
    measurement_wait = measurement_actions.add_parser("wait")
    measurement_wait.add_argument("--ip")
    measurement_wait.add_argument("--timeout", type=float)
    measurement_wait.add_argument("--poll-interval", type=float)
    target = commands.add_parser("target")
    target_actions = target.add_subparsers(dest="action", required=True)
    target_capture = target_actions.add_parser("capture")
    target_capture.add_argument("--ip")
    target_capture.add_argument("--timeout", type=float)
    target_capture.add_argument("--poll-interval", type=float)
    api_command = commands.add_parser("api")
    api_actions = api_command.add_subparsers(dest="action", required=True)
    api_serve = api_actions.add_parser("serve")
    api_serve.add_argument("--host", default="127.0.0.1")
    api_serve.add_argument("--port", type=int, default=8000)
    api_serve.add_argument("--cors-origin", action="append", default=[])
    session = commands.add_parser("session")
    session_actions = session.add_subparsers(dest="action", required=True)
    session_capture = session_actions.add_parser("capture")
    session_capture.add_argument("--ip")
    session_capture.add_argument("--timeout", type=float)
    session_capture.add_argument("--poll-interval", type=float)
    session_compare = session_actions.add_parser("compare")
    session_compare.add_argument("--ip")
    session_compare.add_argument("--session-id", required=True)
    session_compare.add_argument("--target-id", required=True, type=int)
    session_compare.add_argument("--sample-id", required=True, type=int)
    session_diagnose = session_actions.add_parser("diagnose")
    session_diagnose.add_argument("--ip")
    session_diagnose.add_argument("--session-id", required=True)
    session_diagnose.add_argument("--target-id", required=True, type=int)
    session_diagnose.add_argument("--sample-id", required=True, type=int)
    session_correction = session_actions.add_parser("correction-needs")
    session_correction.add_argument("--ip")
    session_correction.add_argument("--session-id", required=True)
    session_correction.add_argument("--target-id", required=True, type=int)
    session_correction.add_argument("--sample-id", required=True, type=int)
    session_pigments = session_actions.add_parser("pigment-candidates")
    session_pigments.add_argument("--ip")
    session_pigments.add_argument("--session-id", required=True)
    session_pigments.add_argument("--target-id", required=True, type=int)
    session_pigments.add_argument("--sample-id", required=True, type=int)
    session_pigments.add_argument(
        "--system", required=True, choices=[item.value for item in PaintSystem]
    )
    session_pigments.add_argument(
        "--finish", required=True, choices=[item.value for item in FinishType]
    )
    session_adjustment = session_actions.add_parser("adjustment")
    adjustment_actions = session_adjustment.add_subparsers(
        dest="adjustment_action", required=True
    )
    adjustment_start = adjustment_actions.add_parser("start")
    adjustment_start.add_argument("--ip")
    adjustment_start.add_argument("--session-id", required=True)
    adjustment_start.add_argument("--target-id", required=True, type=int)
    adjustment_start.add_argument("--before-id", required=True, type=int)
    adjustment_start.add_argument(
        "--system", required=True, choices=[item.value for item in PaintSystem]
    )
    adjustment_start.add_argument(
        "--finish", required=True, choices=[item.value for item in FinishType]
    )
    adjustment_start.add_argument("--volume-ml", required=True)
    adjustment_start.add_argument(
        "--component", required=True, action="append", type=_component_argument
    )
    adjustment_start.add_argument("--reason", required=True)
    adjustment_start.add_argument("--base")
    adjustment_start.add_argument("--color-description")
    for command in (adjustment_start,):
        command.add_argument("--timeout", type=float)
        command.add_argument("--poll-interval", type=float)
        command.add_argument("--pending-file", default="data/pending_adjustment.json")
        command.add_argument("--dataset-file", default="data/adjustments.csv")
        command.add_argument(
            "--components-file", default="data/adjustment_components.csv"
        )
        command.add_argument(
            "--visual-result",
            default=VisualResult.UNKNOWN.value,
            choices=[item.value for item in VisualResult],
        )
        command.add_argument(
            "--trial-status",
            default=OperatorTrialStatus.UNKNOWN.value,
            choices=[item.value for item in OperatorTrialStatus],
        )
        command.add_argument("--observations")
    adjustment_after = adjustment_actions.add_parser("capture-after")
    adjustment_after.add_argument("--ip")
    adjustment_after.add_argument("--timeout", type=float)
    adjustment_after.add_argument("--poll-interval", type=float)
    adjustment_after.add_argument("--pending-file", default="data/pending_adjustment.json")
    adjustment_after.add_argument("--dataset-file", default="data/adjustments.csv")
    adjustment_after.add_argument(
        "--components-file", default="data/adjustment_components.csv"
    )
    adjustment_after.add_argument(
        "--visual-result",
        default=VisualResult.UNKNOWN.value,
        choices=[item.value for item in VisualResult],
    )
    adjustment_after.add_argument(
        "--trial-status",
        default=OperatorTrialStatus.UNKNOWN.value,
        choices=[item.value for item in OperatorTrialStatus],
    )
    adjustment_after.add_argument("--observations")
    adjustment_abandon = adjustment_actions.add_parser("abandon")
    adjustment_abandon.add_argument("--pending-file", default="data/pending_adjustment.json")
    adjustment_abandon.add_argument("--reason", required=True)
    return parser


def _print_info(info) -> None:
    print(f"Manufacturer: {info.manufacturer}")
    print(f"Model: {info.model or '-'}")
    print(f"Serial: {info.serial or '-'}")
    print(f"Firmware: {info.firmware or '-'}")
    print(f"IP: {info.ip}")


def _print_measurement(measurement) -> None:
    print(f"Measurement #{measurement.measurement_id}")
    print(f"Name: {measurement.name or '-'}")
    print(f"GUID: {measurement.guid or '-'}")
    print(f"Timestamp: {measurement.timestamp_raw or '-'}")
    for angle, lab in measurement.angles.items():
        print(f"{int(angle)}\u00b0")
        print(f"L* {lab.L}")
        print(f"a* {lab.a}")
        print(f"b* {lab.b}")
    print("Validation: COMPLETE")


def _confirmed(prompt: str) -> bool:
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"yes", "y", "sim", "s"}


def _print_adjustment_trial(trial) -> None:
    print("ADJUSTMENT COMPLETED")
    print(f"Adjustment: {trial.adjustment_id}")
    print(f"Before: Measurement #{trial.before.measurement_id}")
    print(f"After: Measurement #{trial.after.measurement_id}")
    print(f"Volume: {format(trial.volume_ml, 'f')} ml")
    for component in trial.components:
        print(f"Component: {component.pigment_code} — {format(component.quantity_g, 'f')} g")
    for angle in MeasurementAngle:
        response = trial.observed_response_by_angle[angle]
        before = trial.before_comparison.angles[angle]
        after = trial.after_comparison.angles[angle]
        outcome = trial.outcome_by_angle[angle]
        print(f"{int(angle)}°")
        print(
            "Observed response AFTER - BEFORE: "
            f"L {response.response_l:+.8f}, "
            f"a {response.response_a:+.8f}, "
            f"b {response.response_b:+.8f}"
        )
        print(
            "Error BEFORE - TARGET: "
            f"ΔL {before.delta_l:+.8f}, Δa {before.delta_a:+.8f}, "
            f"Δb {before.delta_b:+.8f}, ΔE76 {before.delta_e76:.8f}"
        )
        print(
            "Error AFTER - TARGET: "
            f"ΔL {after.delta_l:+.8f}, Δa {after.delta_a:+.8f}, "
            f"Δb {after.delta_b:+.8f}, ΔE76 {after.delta_e76:.8f}"
        )
        print(
            "Outcome: "
            f"L={outcome.lightness_outcome.name}, "
            f"a={outcome.red_green_outcome.name}, "
            f"b={outcome.yellow_blue_outcome.name}, "
            f"ΔE={outcome.delta_e_outcome.name}"
        )
    print(f"Worst angle before: {int(trial.worst_angle_before)}°")
    print(f"Worst angle after: {int(trial.worst_angle_after)}°")
    assessment = trial.assessment
    print(
        f"Instrument verdict: {assessment.verdict.name} "
        f"(worst ΔE76 {assessment.worst_delta_e_before:.3f} -> "
        f"{assessment.worst_delta_e_after:.3f})"
    )
    if assessment.overshoot_detected:
        print("Warning: at least one axis crossed the target and ended farther away (overshoot).")
    if assessment.wrong_direction_detected:
        print("Warning: at least one axis moved away from the target (wrong direction).")


def _capture_and_export_adjustment(
    args,
    service,
    workflow: AdjustmentWorkflow,
    pending,
) -> int:
    session = ColorSession.create(
        pending.instrument_serial,
        uuid_factory=lambda: pending.session_id,
    ).with_target(pending.target).with_sample(pending.before)
    request = workflow.retry_after_capture(pending)
    print("Adjustment status: APPLIED_WAITING_FOR_AFTER")
    print("AJUSTE JÁ REGISTRADO COMO APLICADO.")
    print("NÃO ADICIONE O PIGMENTO NOVAMENTE.")
    print("Apenas prepare/seque a chapinha corretamente e faça UMA nova leitura AFTER.")
    try:
        result = workflow.capture_after(
            session,
            AdjustmentHistory(),
            request,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
            visual_result=VisualResult(args.visual_result),
            operator_status=OperatorTrialStatus(args.trial_status),
            observations=args.observations,
        )
    except NewMeasurementTimeoutError:
        print("AFTER TIMEOUT")
        print("AJUSTE JÁ REGISTRADO COMO APLICADO.")
        print("NÃO ADICIONE O PIGMENTO NOVAMENTE. Apenas refaça a leitura AFTER.")
        return 3
    except MeasurementWaitCancelledError:
        print("AFTER capture cancelled. Applied adjustment remains pending.")
        print("NÃO ADICIONE O PIGMENTO NOVAMENTE.")
        return 4
    AdjustmentDatasetExporter().append(
        result.trial,
        Path(args.dataset_file),
        Path(args.components_file),
    )
    workflow.acknowledge_completed(result.trial.adjustment_id)
    _print_adjustment_trial(result.trial)
    print(f"Dataset: {args.dataset_file}")
    print(f"Components dataset: {args.components_file}")
    print("MANDACOR did NOT calculate or recommend this dosage.")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("MANDACOR_DEBUG") == "1" else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    args = _parser().parse_args()
    if args.group == "doctor":
        from mandacor.application.diagnostics import collect_diagnostics, format_diagnostics

        report = collect_diagnostics(
            config_path=Path(args.config),
            pending_path=Path(args.pending_file),
            data_directory=Path(args.data_dir),
            project_root=Path.cwd(),
        )
        print(format_diagnostics(report))
        return 0 if report.configuration == report.recovery == report.golden == "PASS" else 2
    if args.group == "dataset" and args.action == "export-formula-training":
        from mandacor.application.formula_training_dataset import (
            FormulaTrainingDatasetExporter,
        )
        from mandacor.infrastructure.storage.formula_sqlite import SqliteFormulaCatalog

        result = FormulaTrainingDatasetExporter().export(
            SqliteFormulaCatalog(Path(args.catalog)),
            Path(args.output),
            eligible_only=not args.include_review,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    repository = JsonConfigurationRepository(Path(args.config))
    service = InstrumentService(repository)
    try:
        if args.group == "api" and args.action == "serve":
            import uvicorn

            from mandacor.api.app import create_app

            api_config = ApiConfig(
                host=args.host,
                port=args.port,
                cors_origins=tuple(args.cors_origin),
            )
            if api_config.host in {"0.0.0.0", "::"}:
                print("WARNING: MANDACOR API is exposed to the local network.")
            print(f"MANDACOR API: http://{api_config.host}:{api_config.port}")
            uvicorn.run(
                create_app(settings=api_config),
                host=api_config.host,
                port=api_config.port,
            )
            return 0
        if args.group == "instrument" and args.action == "discover":
            print("Searching for BYK instruments...")
            instruments = service.discover_instruments()
            print(f"Found {len(instruments)} instrument(s)")
            for instrument in instruments:
                print(f"Manufacturer: {instrument.manufacturer}")
                print(f"IP: {instrument.ip}")
                print(f"Discovery source: {instrument.source}")
            return 0 if instruments else 2
        if args.group == "instrument" and args.action in ("connect", "info"):
            info = service.connect_manual(args.ip) if getattr(args, "ip", None) else service.connect_auto()
            print("CONNECTED")
            _print_info(info)
            return 0
        if args.group == "instrument" and args.action == "config":
            config = service.config
            if args.mode or args.ip or args.discovery_address or args.local_interface:
                config = replace(
                    config,
                    mode=ConnectionMode(args.mode) if args.mode else config.mode,
                    instrument_ip=args.ip if args.ip is not None else config.instrument_ip,
                    discovery_address=(
                        args.discovery_address
                        if args.discovery_address is not None
                        else config.discovery_address
                    ),
                    local_interface=(
                        args.local_interface
                        if args.local_interface is not None
                        else config.local_interface
                    ),
                )
                service.configure(config)
            output = asdict(config)
            output["mode"] = config.mode.value
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        if args.group == "measurement":
            service.connect_manual(args.ip) if args.ip else service.connect_auto()
            if args.action == "list":
                references = service.list_measurements()
                print("Measurements:")
                print("ID\tName\tGUID")
                for reference in references:
                    print(
                        f"{reference.measurement_id}\t"
                        f"{reference.name or '-'}\t{reference.guid or '-'}"
                    )
                return 0
            if args.action == "wait":
                snapshot = service.create_measurement_snapshot()
                print(f"Current measurements: {len(snapshot.identities)}")
                print("Snapshot created.")
                print("Faça uma NOVA leitura no espectrofotômetro.")
                print("Waiting...")
                started = time.monotonic()
                try:
                    measurement = service.wait_for_new_measurement(
                        snapshot,
                        timeout=args.timeout,
                        poll_interval=args.poll_interval,
                    )
                except NewMeasurementTimeoutError as error:
                    print(
                        "Nenhuma nova medição foi detectada dentro de "
                        f"{error.elapsed:.1f} segundos."
                    )
                    return 3
                except MeasurementWaitCancelledError:
                    print("Espera por nova medição cancelada.")
                    return 4
                print("NEW MEASUREMENT DETECTED")
                _print_measurement(measurement)
                print(f"Elapsed: {time.monotonic() - started:.1f} s")
                return 0
            measurement = (
                service.get_measurement(args.measurement_id)
                if args.action == "get"
                else service.get_latest_measurement()
            )
            _print_measurement(measurement)
            return 0
        if args.group == "target" and args.action == "capture":
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            session = ColorSession.create(info.serial)
            capture_service = CaptureTargetService(
                service,
                instrument_serial=info.serial,
            )
            print("MANDACOR")
            print(f"Instrument: {info.manufacturer} {info.model or '-'}")
            print("Status: CONNECTED")
            print(f"Session: {session.session_id}")
            print("Preparing target capture...")
            request = capture_service.prepare_target_capture(session)
            print("Snapshot created.")
            print("Faça agora a leitura da COR ALVO.")
            print("Waiting...")
            try:
                result = capture_service.capture_target(
                    session,
                    request,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                )
            except NewMeasurementTimeoutError as error:
                print(
                    "Nenhuma nova medição de alvo foi detectada dentro de "
                    f"{error.elapsed:.1f} segundos."
                )
                return 3
            except MeasurementWaitCancelledError:
                print("Captura da cor alvo cancelada.")
                return 4
            print("TARGET CAPTURED")
            print(f"Session: {result.session.session_id}")
            _print_measurement(result.measurement)
            print(f"Elapsed: {result.elapsed:.1f} s")
            return 0
        if args.group == "session" and args.action == "capture":
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            session = ColorSession.create(info.serial)
            target_service = CaptureTargetService(service, instrument_serial=info.serial)
            sample_service = CaptureSampleService(service, instrument_serial=info.serial)
            print("MANDACOR")
            print(f"Instrument: {info.manufacturer} {info.model or '-'}")
            print("Status: CONNECTED")
            print(f"Session: {session.session_id}")
            target_request = target_service.prepare_target_capture(session)
            print("Snapshot da COR ALVO criado.")
            print("Faça agora UMA leitura da COR ALVO.")
            try:
                target_result = target_service.capture_target(
                    session,
                    target_request,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                )
            except NewMeasurementTimeoutError as error:
                print(
                    "Nenhuma nova medição de alvo foi detectada dentro de "
                    f"{error.elapsed:.1f} segundos."
                )
                return 3
            except MeasurementWaitCancelledError:
                print("Captura da cor alvo cancelada.")
                return 4
            session = target_result.session
            print("TARGET CAPTURED")
            print(f"Target: Measurement #{session.target.measurement_id}")
            sample_request = sample_service.prepare_sample_capture(session)
            print("Snapshot da TINTA / AMOSTRA criado.")
            print("Faça agora UMA leitura da TINTA / AMOSTRA.")
            try:
                sample_result = sample_service.capture_sample(
                    session,
                    sample_request,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                )
            except NewMeasurementTimeoutError as error:
                print(
                    "Nenhuma nova medição de amostra foi detectada dentro de "
                    f"{error.elapsed:.1f} segundos."
                )
                return 3
            except MeasurementWaitCancelledError:
                print("Captura da tinta/amostra cancelada.")
                return 4
            session = sample_result.session
            print("SAMPLE CAPTURED")
            _print_measurement(sample_result.measurement)
            print(f"Session: {session.session_id}")
            print(f"Target: Measurement #{session.target.measurement_id}")
            print(f"Sample: Measurement #{session.sample.measurement_id}")
            print(f"Session state: {session.state.value.upper()}")
            return 0
        if args.group == "session" and args.action == "compare":
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            target = service.get_measurement(args.target_id)
            sample = service.get_measurement(args.sample_id)
            session_id = uuid.UUID(args.session_id)
            session = ColorSession.create(
                info.serial,
                uuid_factory=lambda: session_id,
            ).with_target(target).with_sample(sample)
            comparison = compare_session(session)
            print("MANDACOR")
            print("COLOR COMPARISON")
            print(f"Session: {comparison.session_id}")
            print(f"Target: Measurement #{comparison.target_measurement_id}")
            print(f"Sample: Measurement #{comparison.sample_measurement_id}")
            print("Convention: SAMPLE - TARGET")
            for angle in MeasurementAngle:
                target_lab = target.angles[angle]
                sample_lab = sample.angles[angle]
                delta = comparison.angles[angle]
                print(f"{int(angle)}°")
                print(
                    f"Target: L* {target_lab.L:.8f} "
                    f"a* {target_lab.a:.8f} b* {target_lab.b:.8f}"
                )
                print(
                    f"Sample: L* {sample_lab.L:.8f} "
                    f"a* {sample_lab.a:.8f} b* {sample_lab.b:.8f}"
                )
                print(
                    f"Delta: ΔL {delta.delta_l:+.8f} "
                    f"Δa {delta.delta_a:+.8f} "
                    f"Δb {delta.delta_b:+.8f} "
                    f"ΔE76 {delta.delta_e76:.8f}"
                )
            print("Status: COMPARISON CALCULATED")
            return 0
        if args.group == "session" and args.action == "diagnose":
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            target = service.get_measurement(args.target_id)
            sample = service.get_measurement(args.sample_id)
            session_id = uuid.UUID(args.session_id)
            session = ColorSession.create(
                info.serial,
                uuid_factory=lambda: session_id,
            ).with_target(target).with_sample(sample)
            comparison = compare_session(session)
            diagnosis = diagnose_comparison(comparison)
            direction_labels = {
                "lighter": "AMOSTRA MAIS CLARA",
                "darker": "AMOSTRA MAIS ESCURA",
                "redder": "AMOSTRA MAIS VERMELHA",
                "greener": "AMOSTRA MAIS VERDE",
                "yellower": "AMOSTRA MAIS AMARELA",
                "bluer": "AMOSTRA MAIS AZUL",
                "equal": "MESMO VALOR MATEMÁTICO",
                "mixed": "MISTO",
            }
            print("MANDACOR")
            print("COLOR DIAGNOSIS")
            print("Convention: SAMPLE - TARGET")
            print(f"Session: {diagnosis.session_id}")
            print(f"Target: Measurement #{diagnosis.target_measurement_id}")
            print(f"Sample: Measurement #{diagnosis.sample_measurement_id}")
            for angle in MeasurementAngle:
                item = diagnosis.angle_diagnoses[angle]
                print(f"{int(angle)}°")
                print(
                    f"ΔL {item.delta_l:+.8f}: "
                    f"{direction_labels[item.lightness_direction.value]}"
                )
                print(
                    f"Δa {item.delta_a:+.8f}: "
                    f"{direction_labels[item.red_green_direction.value]}"
                )
                print(
                    f"Δb {item.delta_b:+.8f}: "
                    f"{direction_labels[item.yellow_blue_direction.value]}"
                )
                print(f"Dominant axis: {item.dominant_axis.value.upper()}")
                print(f"ΔE76: {item.delta_e76:.8f}")
            print(f"Worst angle: {int(diagnosis.worst_angle)}°")
            print(
                "Ranking: "
                + " > ".join(
                    f"{int(angle)}°" for angle in diagnosis.angles_by_delta_e_descending
                )
            )
            print(
                "Front: "
                f"L={diagnosis.front_summary.lightness.value}, "
                f"a={diagnosis.front_summary.red_green.value}, "
                f"b={diagnosis.front_summary.yellow_blue.value}"
            )
            mid = diagnosis.mid_angle_summary
            print(
                "Mid 45°: "
                f"L={mid.lightness_direction.value}, "
                f"a={mid.red_green_direction.value}, "
                f"b={mid.yellow_blue_direction.value}"
            )
            print(
                "Flop: "
                f"L={diagnosis.flop_summary.lightness.value}, "
                f"a={diagnosis.flop_summary.red_green.value}, "
                f"b={diagnosis.flop_summary.yellow_blue.value}"
            )
            print(
                "Patterns: "
                f"L={diagnosis.global_patterns.lightness.value}, "
                f"a={diagnosis.global_patterns.red_green.value}, "
                f"b={diagnosis.global_patterns.yellow_blue.value}, "
                f"L trend={diagnosis.global_patterns.lightness_trend.value}"
            )
            print("Status: DIAGNOSIS CALCULATED")
            return 0
        if args.group == "session" and args.action == "correction-needs":
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            target = service.get_measurement(args.target_id)
            sample = service.get_measurement(args.sample_id)
            session_id = uuid.UUID(args.session_id)
            session = ColorSession.create(
                info.serial,
                uuid_factory=lambda: session_id,
            ).with_target(target).with_sample(sample)
            comparison = compare_session(session)
            diagnosis = diagnose_comparison(comparison)
            correction = derive_correction_need(diagnosis, comparison)
            print("MANDACOR")
            print("BENCH COLOR DIAGNOSIS")
            print(f"Session: {correction.session_id}")
            print(f"Target: Measurement #{correction.target_measurement_id}")
            print(f"Sample: Measurement #{correction.sample_measurement_id}")
            print("Convention: SAMPLE - TARGET")
            for angle in MeasurementAngle:
                observed = diagnosis.angle_diagnoses[angle]
                need = correction.by_angle[angle]
                print(f"{int(angle)}° — {('FRONT' if int(angle) in (15, 25) else 'MID' if int(angle) == 45 else 'FLOP')}")
                print(
                    "Observed: "
                    f"{observed.lightness_direction.name}, "
                    f"{observed.red_green_direction.name}, "
                    f"{observed.yellow_blue_direction.name}"
                )
                print(
                    "Needs: "
                    f"{need.lightness_action.name}, "
                    f"{need.red_green_action.name}, "
                    f"{need.yellow_blue_action.name}"
                )
                print(
                    "Correction vector: "
                    f"L {need.correction_delta_l:+.8f}, "
                    f"a {need.correction_delta_a:+.8f}, "
                    f"b {need.correction_delta_b:+.8f}"
                )
            for label, summary in (
                ("FRONT", correction.front),
                ("MID 45°", correction.mid),
                ("FLOP", correction.flop),
            ):
                print(label)
                print(
                    f"L={summary.lightness_action.name}, "
                    f"a={summary.red_green_action.name}, "
                    f"b={summary.yellow_blue_action.name}"
                )
            primary = correction.primary_issue
            print("PRIMARY ISSUE")
            print(f"Angle: {int(primary.angle)}°")
            print(f"Group: {primary.group.name}")
            print(f"Axis: {primary.axis.name}")
            print(f"Need: {primary.action.name if primary.action is not None else 'TIE'}")
            flags = correction.multiangle_flags
            print("MULTIANGLE FLAGS")
            print(f"Lightness uniform: {'NO' if flags.lightness_action_varies_by_angle else 'YES'}")
            print(f"Red/Green uniform: {'NO' if flags.red_green_action_varies_by_angle else 'YES'}")
            print(f"Yellow/Blue uniform: {'NO' if flags.yellow_blue_action_varies_by_angle else 'YES'}")
            print("No pigment recommendation available in Gate 8.")
            return 0
        if args.group == "session" and args.action == "pigment-candidates":
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            target = service.get_measurement(args.target_id)
            sample = service.get_measurement(args.sample_id)
            session_id = uuid.UUID(args.session_id)
            session = ColorSession.create(
                info.serial,
                uuid_factory=lambda: session_id,
            ).with_target(target).with_sample(sample)
            comparison = compare_session(session)
            diagnosis = diagnose_comparison(comparison)
            correction = derive_correction_need(diagnosis, comparison)
            context = PaintContext(PaintSystem(args.system), FinishType(args.finish))
            recommendation = evaluate_pigment_candidates(
                correction,
                context,
                build_skylack_knowledge_base(),
            )
            print("MANDACOR")
            print("QUALITATIVE PIGMENT ANALYSIS")
            print(f"Session: {correction.session_id}")
            print(f"System: {context.system.name}")
            print(f"Finish: {context.finish_type.name}")
            primary = correction.primary_issue
            print(
                f"Primary issue: {int(primary.angle)}° / {primary.axis.name} / "
                f"{primary.action.name if primary.action is not None else 'TIE'}"
            )
            print("MULTIANGLE NEEDS")
            for label, summary in (
                ("Front", correction.front),
                ("45°", correction.mid),
                ("Flop", correction.flop),
            ):
                print(
                    f"{label}: L={summary.lightness_action.name}, "
                    f"a={summary.red_green_action.name}, "
                    f"b={summary.yellow_blue_action.name}"
                )
            print("CANDIDATES")
            for index, candidate in enumerate(recommendation.candidates, start=1):
                print(f"{index}. {candidate.pigment_code} — {candidate.status.name}")
                print("Why: " + " ".join(candidate.rationale))
                helps = ", ".join(
                    f"{int(item.angle)}°/{item.axis.name}/{item.need.name}"
                    for item in candidate.matched_needs
                ) or "NONE"
                conflicts = ", ".join(
                    f"{int(item.angle)}°/{item.axis.name}/{item.pigment_effect.name}"
                    for item in candidate.conflicts
                ) or "NONE"
                risks = ", ".join(item.name for item in candidate.risks) or "NONE"
                print(f"Helps: {helps}")
                print(f"Conflicts: {conflicts}")
                print(f"Risks: {risks}")
            print("REJECTED")
            for candidate in recommendation.rejected_candidates:
                reason = "; ".join(candidate.contraindications or candidate.rationale)
                print(f"{candidate.pigment_code}: {candidate.status.name} — {reason}")
            print("IMPORTANT")
            for warning in recommendation.warnings:
                print(warning)
            print("No dosage has been calculated.")
            print("Bench test required before physical adjustment.")
            return 0
        if args.group == "session" and args.action == "adjustment":
            pending_repository = JsonPendingAdjustmentRepository(
                Path(args.pending_file)
            )
            existing = pending_repository.load()
            if args.adjustment_action == "abandon":
                if existing is None:
                    print("No pending adjustment exists.")
                    return 2
                print("Existe um ajuste físico aplicado pendente de leitura AFTER.")
                print(f"Adjustment: {existing.adjustment_id}")
                print("This action records ABANDONED_AFTER_APPLICATION; it does not erase the fact.")
                if not _confirmed("Confirm explicit abandonment? [yes/no] "):
                    print("Abandonment cancelled; pending adjustment preserved.")
                    return 4
                abandoned = existing.abandon_after_application(args.reason)
                pending_repository.save(abandoned)
                print("Status: ABANDONED_AFTER_APPLICATION")
                return 0
            if args.adjustment_action == "start":
                if existing is not None:
                    print("Existe um ajuste físico pendente de leitura AFTER.")
                    print(f"Adjustment: {existing.adjustment_id}")
                    print("Capture or explicitly abandon it before starting another adjustment.")
                    return 5
                info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
                target = service.get_measurement(args.target_id)
                before = service.get_measurement(args.before_id)
                session_id = uuid.UUID(args.session_id)
                session = ColorSession.create(
                    info.serial,
                    uuid_factory=lambda: session_id,
                ).with_target(target).with_sample(before)
                print("MANDACOR — EXPERIMENTAL ADJUSTMENT")
                print(f"Session: {session.session_id}")
                print(f"Target: Measurement #{target.measurement_id}")
                print(f"Current sample BEFORE: Measurement #{before.measurement_id}")
                if not _confirmed(
                    "Confirm TARGET and BEFORE represent the current physical job? [yes/no] "
                ):
                    print("Adjustment not planned.")
                    return 4
                pending = plan_adjustment(
                    session,
                    PaintContext(PaintSystem(args.system), FinishType(args.finish)),
                    args.volume_ml,
                    tuple(args.component),
                    args.reason,
                    build_skylack_knowledge_base(),
                    base_identifier=args.base,
                    color_description=args.color_description,
                )
                print("SUMMARY — operator-provided facts")
                print(f"System: {pending.paint_context.system.name}")
                print(f"Finish: {pending.paint_context.finish_type.name}")
                print(f"Volume: {format(pending.volume_ml, 'f')} ml")
                for component in pending.components:
                    print(
                        f"Component: {component.pigment_code} — "
                        f"{format(component.quantity_g, 'f')} g"
                    )
                print("MANDACOR did NOT calculate this dosage.")
                print("Apply only the quantity YOU decided to use.")
                if not _confirmed(
                    "Confirm that the physical adjustment has already been applied? [yes/no] "
                ):
                    print("Cancelled before application; no experimental trial was created.")
                    return 4
                workflow = AdjustmentWorkflow(
                    service,
                    pending_repository=pending_repository,
                )
                applied = workflow.confirm_applied(pending)
                return _capture_and_export_adjustment(
                    args, service, workflow, applied
                )
            if existing is None:
                print("No applied pending adjustment exists.")
                return 2
            if existing.lifecycle is not AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER:
                print(f"Pending record status is {existing.lifecycle.name}; AFTER capture refused.")
                return 5
            info = service.connect_manual(args.ip) if args.ip else service.connect_auto()
            if (
                existing.instrument_serial is not None
                and info.serial is not None
                and existing.instrument_serial != info.serial
            ):
                raise ValueError("connected instrument differs from pending adjustment")
            print("Existe um ajuste físico pendente de leitura AFTER.")
            print(f"Adjustment: {existing.adjustment_id}")
            workflow = AdjustmentWorkflow(
                service,
                pending_repository=pending_repository,
            )
            return _capture_and_export_adjustment(
                args, service, workflow, existing
            )
    except (InstrumentError, OSError, ValueError) as error:
        logging.getLogger("mandacor.cli").error("%s", error)
        return 1
    finally:
        service.disconnect()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
from mandacor.application.comparison_service import compare_session
