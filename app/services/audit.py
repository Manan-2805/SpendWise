from datetime import date
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditRepository

logger = structlog.get_logger()


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditRepository(db)

    def _sanitize(self, val: Any) -> Any:
        if isinstance(val, dict):
            return {k: self._sanitize(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self._sanitize(x) for x in val]
        elif isinstance(val, Decimal):
            return str(val)
        elif isinstance(val, date):
            return val.isoformat()
        return val

    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: str | int,
        user_id: int | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        """Log an action to the database via AuditRepository and emit a structured log."""
        ctx = structlog.contextvars.get_contextvars()
        correlation_id = ctx.get("correlation_id", "SYSTEM")
        ip_address = ctx.get("client_ip")
        user_agent = ctx.get("user_agent")

        sanitized_old = self._sanitize(old_values) if old_values is not None else None
        sanitized_new = self._sanitize(new_values) if new_values is not None else None

        await self.repo.create_log(
            user_id=user_id,
            correlation_id=correlation_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            old_values=sanitized_old,
            new_values=sanitized_new,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "audit_event",
            action=action,
            resource=f"{resource_type}:{resource_id}",
            user_id=user_id if user_id is not None else "system",
        )
