"""Domain ports for Benchbook services."""

from __future__ import annotations

from typing import Any, Protocol

from benchbook.domain.models import AdviceResponse, Job


class AdvisoryPort(Protocol):
    """Small application port for advisory generation conforming to ADR-004."""

    async def generate_advice(
        self,
        workspace_id: str,
        job: Job,
        operation: str,
        expected_version: int,
        idempotency_key: str | None = None,
        job_details: dict[str, Any] | None = None,
    ) -> AdviceResponse:
        """Provide AI advisory grounded in the authorized job snapshot."""
        ...
