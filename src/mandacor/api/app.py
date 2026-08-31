from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mandacor import __version__

from mandacor.api.schemas import (
    AbandonAdjustmentRequest,
    AdjustmentCreateRequest,
    AdjustmentFeedbackRequest,
    ConnectRequest,
    PaintContextRequest,
    WaitOperationRequest,
    adjustment_dict,
    comparison_dict,
    correction_dict,
    diagnosis_dict,
    discovered_instrument_dict,
    instrument_info_dict,
    measurement_dict,
    measurement_reference_dict,
    pigment_recommendation_dict,
    session_dict,
)
from mandacor.api.service import (
    ApiError,
    CaptureType,
    InMemorySessionRepository,
    MandacorApiService,
)
from mandacor.application.adjustment_dataset import AdjustmentDatasetExporter
from mandacor.application.instrument_service import InstrumentService
from mandacor.config import ApiConfig
from mandacor.domain.adjustments import AdjustmentComponent
from mandacor.domain.measurements import MeasurementNotFoundError
from mandacor.domain.pigments import PaintContext
from mandacor.infrastructure.config.json_config import JsonConfigurationRepository
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentError
from mandacor.infrastructure.storage.pending_adjustment_json import (
    JsonPendingAdjustmentRepository,
)
from mandacor.infrastructure.storage.session_json import JsonSessionRepository


logger = logging.getLogger(__name__)
API_VERSION = "v1"


def _error_body(
    code: str,
    message: str,
    details: dict | None = None,
    *,
    request_id: str | None = None,
):
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    if request_id:
        body["error"]["request_id"] = request_id
    return body


def _operation_dict(operation):
    return {
        "operation_id": str(operation.operation_id),
        "session_id": str(operation.session_id),
        "type": operation.capture_type.name,
        "status": operation.status.name,
        "created_at": operation.created_at.isoformat(),
        "measurement_id": operation.result_measurement_id,
        "error_code": operation.error_code,
    }


def _default_service() -> MandacorApiService:
    instrument = InstrumentService(
        JsonConfigurationRepository(Path("config/mandacor.json"))
    )
    pending = JsonPendingAdjustmentRepository(Path("data/pending_adjustment.json"))
    sessions = InMemorySessionRepository(
        JsonSessionRepository(Path("data/sessions.json"))
    )

    def persist_trial(trial):
        AdjustmentDatasetExporter().append(
            trial,
            Path("data/adjustments.csv"),
            Path("data/adjustment_components.csv"),
        )

    return MandacorApiService(
        instrument,
        sessions=sessions,
        pending_repository=pending,
        on_adjustment_complete=persist_trial,
    )


def create_app(
    service: MandacorApiService | None = None,
    *,
    settings: ApiConfig | None = None,
) -> FastAPI:
    api = service or _default_service()
    config = settings or ApiConfig()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("MANDACOR API started")
        try:
            yield
        finally:
            api.shutdown()
            logger.info("MANDACOR API stopped")

    app = FastAPI(
        title="MANDACOR Local API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.mandacor = api
    app.state.api_config = config

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "").strip()
        request_id = supplied[:128] if supplied else str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request event=request_complete request_id=%s method=%s path=%s status=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, error: ApiError):
        request_id = getattr(_.state, "request_id", None)
        return JSONResponse(
            status_code=error.status_code,
            content=_error_body(
                error.code, error.message, error.details, request_id=request_id
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, error: RequestValidationError):
        errors = [
            {
                "type": item.get("type"),
                "location": list(item.get("loc", ())),
                "message": item.get("msg"),
            }
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "REQUEST_VALIDATION_ERROR",
                "request validation failed",
                {"errors": errors},
                request_id=getattr(_.state, "request_id", None),
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.exception(
            "http_request event=unexpected_error request_id=%s path=%s",
            request_id,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "INTERNAL_SERVER_ERROR",
                "an unexpected server error occurred",
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(MeasurementNotFoundError)
    async def measurement_not_found_handler(_: Request, error: MeasurementNotFoundError):
        return JSONResponse(
            status_code=404,
            content=_error_body("MEASUREMENT_NOT_FOUND", str(error)),
        )

    @app.exception_handler(InstrumentError)
    async def instrument_error_handler(_: Request, error: InstrumentError):
        return JSONResponse(
            status_code=503,
            content=_error_body("INSTRUMENT_UNAVAILABLE", str(error)),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, error: ValueError):
        return JSONResponse(
            status_code=400,
            content=_error_body("INVALID_REQUEST", str(error)),
        )

    @app.get("/health")
    @app.get("/api/v1/health")
    def health():
        return {
            "status": "ok",
            "service": "mandacor",
            "version": __version__,
            "api_version": API_VERSION,
            "recovery": "ERROR" if api.recovery_error else "OK",
            "recovery_error": api.recovery_error,
        }

    @app.get("/api/v1/instrument/status")
    def instrument_status():
        connected, info = api.instrument_status()
        return {
            "connected": connected,
            "instrument": instrument_info_dict(info) if info else None,
        }

    @app.post("/api/v1/instrument/discover")
    def instrument_discover():
        return {
            "instruments": [
                discovered_instrument_dict(item) for item in api.discover()
            ]
        }

    @app.post("/api/v1/instrument/connect")
    def instrument_connect(body: ConnectRequest):
        state, info, found = api.connect(body.mode, body.host)
        return {
            "state": state,
            "connected": state == "CONNECTED",
            "instrument": instrument_info_dict(info) if info else None,
            "instruments": [discovered_instrument_dict(item) for item in found],
        }

    @app.post("/api/v1/instrument/disconnect")
    def instrument_disconnect():
        api.disconnect()
        return {"connected": False}

    @app.get("/api/v1/measurements")
    def measurements():
        api.require_connected()
        return [measurement_reference_dict(item) for item in api.instrument.list_measurements()]

    @app.get("/api/v1/measurements/{measurement_id}")
    def measurement(measurement_id: int):
        api.require_connected()
        return measurement_dict(api.instrument.get_measurement(measurement_id))

    @app.post("/api/v1/sessions", status_code=201)
    def create_session():
        return session_dict(api.create_session())

    @app.get("/api/v1/sessions/{session_id}")
    def get_session(session_id: uuid.UUID):
        return session_dict(api.sessions.get(session_id))

    @app.post("/api/v1/sessions/{session_id}/target/prepare", status_code=201)
    def prepare_target(session_id: uuid.UUID):
        return _operation_dict(api.prepare_capture(session_id, CaptureType.TARGET))

    @app.post("/api/v1/sessions/{session_id}/sample/prepare", status_code=201)
    def prepare_sample(session_id: uuid.UUID):
        return _operation_dict(api.prepare_capture(session_id, CaptureType.SAMPLE))

    @app.post("/api/v1/sessions/{session_id}/target/replace-with-latest")
    def replace_target_with_latest(session_id: uuid.UUID):
        return session_dict(api.replace_with_latest(session_id, CaptureType.TARGET))

    @app.post("/api/v1/sessions/{session_id}/sample/replace-with-latest")
    def replace_sample_with_latest(session_id: uuid.UUID):
        return session_dict(api.replace_with_latest(session_id, CaptureType.SAMPLE))

    @app.get("/api/v1/operations/{operation_id}")
    def get_operation(operation_id: uuid.UUID):
        return _operation_dict(api.operations.get(operation_id))

    @app.post("/api/v1/operations/{operation_id}/wait")
    def wait_operation(operation_id: uuid.UUID, body: WaitOperationRequest | None = None):
        request = body or WaitOperationRequest()
        return _operation_dict(
            api.wait_operation(
                operation_id,
                timeout=request.timeout,
                poll_interval=request.poll_interval,
            )
        )

    @app.post("/api/v1/operations/{operation_id}/cancel")
    def cancel_operation(operation_id: uuid.UUID):
        return _operation_dict(api.cancel_operation(operation_id))

    @app.get("/api/v1/sessions/{session_id}/comparison")
    def comparison(session_id: uuid.UUID):
        return comparison_dict(api.comparison(session_id))

    @app.get("/api/v1/sessions/{session_id}/diagnosis")
    def diagnosis(session_id: uuid.UUID):
        return diagnosis_dict(api.diagnosis(session_id))

    @app.get("/api/v1/sessions/{session_id}/correction-needs")
    def correction(session_id: uuid.UUID):
        return correction_dict(api.correction(session_id))

    @app.post("/api/v1/sessions/{session_id}/pigment-candidates")
    def pigments(session_id: uuid.UUID, body: PaintContextRequest):
        recommendation = api.pigment_candidates(
            session_id, PaintContext(body.system, body.finish)
        )
        return pigment_recommendation_dict(recommendation)

    @app.post("/api/v1/sessions/{session_id}/adjustments", status_code=201)
    def create_adjustment(session_id: uuid.UUID, body: AdjustmentCreateRequest):
        adjustment = api.create_adjustment(
            session_id,
            PaintContext(body.system, body.finish),
            body.volume_ml,
            tuple(
                AdjustmentComponent(item.pigment_code, item.quantity_g)
                for item in body.components
            ),
            body.operator_reason,
            base_identifier=body.base_identifier,
            color_description=body.color_description,
        )
        return adjustment_dict(adjustment)

    @app.get("/api/v1/sessions/{session_id}/adjustments")
    def list_adjustments(session_id: uuid.UUID):
        api.sessions.get(session_id)
        return [adjustment_dict(item) for item in api.adjustments.for_session(session_id)]

    @app.get("/api/v1/adjustments/pending")
    def get_pending_adjustment():
        pending = api.pending_adjustment()
        return adjustment_dict(pending) if pending else None

    @app.get("/api/v1/adjustments/{adjustment_id}")
    def get_adjustment(adjustment_id: uuid.UUID):
        return adjustment_dict(api.adjustments.get(adjustment_id))

    @app.post("/api/v1/adjustments/{adjustment_id}/confirm-applied")
    def confirm_applied(adjustment_id: uuid.UUID):
        return adjustment_dict(api.confirm_adjustment_applied(adjustment_id))

    @app.post("/api/v1/adjustments/{adjustment_id}/abandon")
    def abandon_adjustment(adjustment_id: uuid.UUID, body: AbandonAdjustmentRequest):
        return adjustment_dict(api.abandon_adjustment(adjustment_id, body.observation))

    @app.post("/api/v1/adjustments/{adjustment_id}/feedback")
    def adjustment_feedback(adjustment_id: uuid.UUID, body: AdjustmentFeedbackRequest):
        return adjustment_dict(
            api.update_adjustment_feedback(
                adjustment_id,
                body.visual_result,
                body.operator_status,
                body.observations,
            )
        )

    @app.post("/api/v1/adjustments/{adjustment_id}/after/prepare", status_code=201)
    def prepare_after(adjustment_id: uuid.UUID):
        return _operation_dict(api.prepare_adjustment_after(adjustment_id))

    @app.post("/api/v1/adjustments/{adjustment_id}/after/retry", status_code=201)
    def retry_after(adjustment_id: uuid.UUID):
        return _operation_dict(api.prepare_adjustment_after(adjustment_id))

    return app
