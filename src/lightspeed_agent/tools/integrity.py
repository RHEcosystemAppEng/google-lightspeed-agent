"""Lightweight data integrity verification for MCP tool results."""

import hashlib
import logging

logger = logging.getLogger(__name__)


def log_response_fingerprint(
    tool_name: str,
    result: str,
    request_id: str = "",
) -> str:
    """Log a SHA-256 fingerprint of an MCP tool result for forensic tracing.

    Args:
        tool_name: Name of the MCP tool that produced the result.
        result: The raw result string.
        request_id: Optional request ID for correlation.

    Returns:
        The hex digest fingerprint.
    """
    fingerprint = hashlib.sha256(result.encode("utf-8")).hexdigest()[:16]
    logger.info(
        "MCP result fingerprint: tool=%s request_id=%s fingerprint=%s length=%d",
        tool_name,
        request_id,
        fingerprint,
        len(result),
    )
    return fingerprint
