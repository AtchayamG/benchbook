"""Benchbook FastAPI Application Setup and Exception Handlers."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from benchbook.config import normalize_assistant_mode, settings
from benchbook.domain.errors import (
    AssistantBusyError,
    AssistantInvalidOutputError,
    AssistantTimeoutError,
    AssistantUnavailableError,
    CapacityExceededError,
    HumanApprovalRequiredError,
    IdempotencyConflictError,
    IneligibleAdviceError,
    InvalidStateTransitionError,
    JobNotFoundError,
    OriginRefusedError,
    SessionExpiredError,
    StateConflictError,
    ValidationError,
    WorkspaceNotFoundError,
)
from benchbook.infrastructure.admission import InferenceAdmissionStore
from benchbook.infrastructure.assistant_adapter import DeterministicAssistantAdapter
from benchbook.infrastructure.store_factory import get_repair_job_store
from benchbook.infrastructure.strands_advisory import StrandsAdvisoryEngine
from benchbook.interfaces.http.routes.advice import router as advice_router
from benchbook.interfaces.http.routes.assistant import router as assistant_router
from benchbook.interfaces.http.routes.health import router as health_router
from benchbook.interfaces.http.routes.jobs import router as jobs_router
from benchbook.interfaces.http.routes.session import router as session_router
from benchbook.interfaces.http.routes.transitions import router as transitions_router


def create_app(
    db_path: str | None = None,
    assistant_mode: str | None = None,
) -> FastAPI:
    """Create and configure Benchbook FastAPI application."""
    store_instance = get_repair_job_store(db_path or settings.database_url)
    mode = normalize_assistant_mode(
        assistant_mode if assistant_mode is not None else settings.assistant_mode
    )
    assistant_instance = DeterministicAssistantAdapter(mode)
    admission_instance = InferenceAdmissionStore(store_instance.db_path)
    advisory_instance = StrandsAdvisoryEngine(
        admission_instance, api_key=settings.groq_api_key, mode=mode
    )

    app = FastAPI(
        title="Benchbook API",
        description="Professional Repair Shop Workflow & Advisory Engine",
        version="0.2.0",
    )
    app.state.store = store_instance
    app.state.assistant = assistant_instance
    app.state.admission_store = admission_instance
    app.state.advisory_engine = advisory_instance
    app.state.assistant_mode = mode
    app.state.inference_configured = mode != "live" or bool(settings.groq_api_key)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(JobNotFoundError)
    async def handle_job_not_found(request: Request, exc: JobNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "JOB_NOT_FOUND", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(WorkspaceNotFoundError)
    async def handle_workspace_not_found(
        request: Request, exc: WorkspaceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "WORKSPACE_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(SessionExpiredError)
    async def handle_session_expired(request: Request, exc: SessionExpiredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "SESSION_EXPIRED", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(OriginRefusedError)
    async def handle_origin_refused(request: Request, exc: OriginRefusedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "ORIGIN_REFUSED", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(CapacityExceededError)
    async def handle_capacity_exceeded(
        request: Request, exc: CapacityExceededError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "CAPACITY_EXCEEDED",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(IneligibleAdviceError)
    async def handle_ineligible_advice(
        request: Request, exc: IneligibleAdviceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "INELIGIBLE_ADVICE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def handle_invalid_transition(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "INVALID_STATE_TRANSITION",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(StateConflictError)
    async def handle_state_conflict(request: Request, exc: StateConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "STATE_CONFLICT", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(IdempotencyConflictError)
    async def handle_idempotency_conflict(
        request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "IDEMPOTENCY_CONFLICT",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(HumanApprovalRequiredError)
    async def handle_human_approval_required(
        request: Request, exc: HumanApprovalRequiredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "HUMAN_APPROVAL_REQUIRED",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "VALIDATION_ERROR", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(AssistantTimeoutError)
    async def handle_assistant_timeout(
        request: Request, exc: AssistantTimeoutError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "ASSISTANT_TIMEOUT", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(AssistantBusyError)
    async def handle_assistant_busy(request: Request, exc: AssistantBusyError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "ASSISTANT_BUSY", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(AssistantUnavailableError)
    async def handle_assistant_unavailable(
        request: Request, exc: AssistantUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "ASSISTANT_UNAVAILABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AssistantInvalidOutputError)
    async def handle_assistant_invalid_output(
        request: Request, exc: AssistantInvalidOutputError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "ASSISTANT_INVALID_OUTPUT",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        path = request.url.path
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            if path.startswith("/api/") or path == "/api":
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "error": "NOT_FOUND",
                        "message": f"API endpoint '{path}' not found.",
                    },
                )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "NOT_FOUND", "message": f"Resource '{path}' not found."},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    # Register Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(transitions_router, prefix="/api")
    app.include_router(advice_router, prefix="/api")
    app.include_router(assistant_router, prefix="/api")

    # Static assets and SPA fallback
    configured_static = os.environ.get("BENCHBOOK_STATIC_DIR")
    if configured_static:
        static_dir = Path(configured_static)
    else:
        repo_root = (
            Path(__file__).resolve().parents[6]
            if len(Path(__file__).resolve().parents) > 6
            else None
        )
        candidates: list[Path] = []
        if repo_root is not None:
            candidates.append(repo_root / "apps" / "web" / "dist")
        candidates.extend(
            [
                Path("/app/apps/web/dist"),
                Path("/app/dist"),
                Path.cwd() / "apps" / "web" / "dist",
            ]
        )
        static_dir = next((p for p in candidates if p.is_dir()), Path("/nonexistent"))

    if static_dir.is_dir() and (static_dir / "index.html").is_file():
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.api_route(
            "/{full_path:path}",
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
            include_in_schema=False,
        )
        async def serve_spa_frontend(request: Request, full_path: str) -> Response:
            cleaned = full_path.lstrip("/")
            if cleaned.startswith("api/") or cleaned == "api":
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "error": "NOT_FOUND",
                        "message": f"API endpoint '/{cleaned}' not found.",
                    },
                )
            if request.method != "GET":
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"error": "NOT_FOUND", "message": f"Resource '/{cleaned}' not found."},
                )
            target = (static_dir / cleaned).resolve()
            if not target.is_relative_to(static_dir.resolve()):
                return JSONResponse(status_code=404, content={"error": "NOT_FOUND"})
            if cleaned and target.is_file():
                return FileResponse(str(target))
            index_file = static_dir / "index.html"
            return FileResponse(str(index_file))

    else:

        @app.api_route(
            "/{full_path:path}",
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
            include_in_schema=False,
        )
        async def fallback_route(full_path: str) -> JSONResponse:
            cleaned = full_path.lstrip("/")
            if cleaned.startswith("api/") or cleaned == "api":
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "error": "NOT_FOUND",
                        "message": f"API endpoint '/{cleaned}' not found.",
                    },
                )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "NOT_FOUND", "message": f"Resource '/{cleaned}' not found."},
            )

    return app


app = create_app()
