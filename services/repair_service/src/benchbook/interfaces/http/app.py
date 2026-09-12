"""Benchbook FastAPI Application Setup and Exception Handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from benchbook.config import settings
from benchbook.domain.errors import (
    AssistantBusyError,
    AssistantInvalidOutputError,
    AssistantTimeoutError,
    AssistantUnavailableError,
    HumanApprovalRequiredError,
    InvalidStateTransitionError,
    JobNotFoundError,
    StateConflictError,
    ValidationError,
)
from benchbook.infrastructure.assistant_adapter import DeterministicAssistantAdapter
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore
from benchbook.interfaces.http.routes.assistant import router as assistant_router
from benchbook.interfaces.http.routes.health import router as health_router
from benchbook.interfaces.http.routes.jobs import router as jobs_router
from benchbook.interfaces.http.routes.transitions import router as transitions_router

# Module-level singletons for dependency injection
store_instance: SqliteRepairJobStore = SqliteRepairJobStore(
    settings.database_url.replace("sqlite:///", "")
)
assistant_instance: DeterministicAssistantAdapter = DeterministicAssistantAdapter(
    settings.assistant_mode
)


def create_app(
    db_path: str | None = None,
    assistant_mode: str | None = None,
) -> FastAPI:
    """Create and configure Benchbook FastAPI application."""
    global store_instance, assistant_instance

    if db_path is not None:
        store_instance = SqliteRepairJobStore(db_path)
    if assistant_mode is not None:
        assistant_instance = DeterministicAssistantAdapter(assistant_mode)

    app = FastAPI(
        title="Benchbook API",
        description="Professional Repair Shop Workflow & Advisory Engine",
        version="0.1.0",
    )

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

    # Register Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(transitions_router, prefix="/api")
    app.include_router(assistant_router, prefix="/api")

    return app


app = create_app()
