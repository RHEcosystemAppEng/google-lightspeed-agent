"""Logging filter to inject audit context from contextvars into log records."""

import logging

from lightspeed_agent.auth.middleware import (
    get_request_id,
    get_request_order_id,
    get_request_org_id,
    get_request_user_id,
)


class AuditContextFilter(logging.Filter):
    """Inject user_id, org_id, order_id, and request_id into every log record.

    Reads values from contextvars set by AuthenticationMiddleware.
    When no authenticated context exists (e.g., startup logs), fields
    default to empty strings so the JSON format is always consistent.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        from lightspeed_agent.config import get_settings

        settings = get_settings()
        if settings.audit_logging_enabled:
            record.user_id = get_request_user_id() or ""
            record.org_id = get_request_org_id() or ""
            record.order_id = get_request_order_id() or ""
            record.request_id = get_request_id() or ""
        else:
            record.user_id = ""
            record.org_id = ""
            record.order_id = ""
            record.request_id = ""
        return True
