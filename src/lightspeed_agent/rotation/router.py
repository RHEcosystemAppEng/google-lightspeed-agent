"""Rotation endpoint router for Secret Manager Pub/Sub events."""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from lightspeed_agent.rotation.gcp import GoogleSecretManagerVersionWriter
from lightspeed_agent.rotation.providers import create_default_registry
from lightspeed_agent.rotation.pubsub_jwt import get_pubsub_jwt_validator
from lightspeed_agent.rotation.workflow import RotationWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Secret Rotation"])

# Module-level workflow singleton (reuses Secret Manager gRPC client across requests)
_workflow = RotationWorkflow(
    secret_writer=GoogleSecretManagerVersionWriter(),
    value_provider=create_default_registry(),
)


@router.post("/rotation")
async def rotation_handler(request: Request) -> JSONResponse:
    """Handle Secret Manager rotation events from Pub/Sub push.

    Request format (Pub/Sub push):
    {
      "message": {
        "messageId": "abc123",
        "data": "<base64>",  # Not used for rotation
        "attributes": {
          "eventType": "SECRET_ROTATE",
          "secretId": "projects/my-project/secrets/redhat-sso-client-secret"
        }
      },
      "subscription": "projects/my-project/subscriptions/secret-rotation-trigger-sub"
    }

    Returns:
        200: Success or ignored events (Pub/Sub acks)
        401: Invalid Pub/Sub OIDC token
        400: Invalid request format
        500: Workflow failures (Pub/Sub retries)
    """
    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Invalid JSON body in rotation request: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    # Extract Pub/Sub message
    message = body.get("message", {})
    if not message:
        logger.warning("Missing 'message' field in rotation request")
        raise HTTPException(status_code=400, detail="Missing Pub/Sub message")

    message_id = message.get("messageId", "unknown")
    attributes = message.get("attributes", {})
    secret_id = attributes.get("secretId", "")

    logger.info(
        "Processing Secret Manager rotation event (event_type=rotation_event_received, "
        "message_id=%s, secret_id=%s)",
        message_id,
        secret_id,
    )

    # Verify Pub/Sub OIDC token
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()

    if not token:
        logger.warning(
            "Missing Authorization header (event_type=rotation_auth_failed, message_id=%s)",
            message_id,
        )
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    validator = get_pubsub_jwt_validator()
    claims = await validator.validate_push_token(token)

    if claims is None:
        logger.warning(
            "Invalid Pub/Sub OIDC token (event_type=rotation_auth_failed, message_id=%s)",
            message_id,
        )
        raise HTTPException(status_code=401, detail="Invalid Pub/Sub token")

    # Call rotation workflow (synchronous)
    try:
        result = _workflow.handle_event(attributes=attributes)
    except Exception as e:
        logger.exception(
            "Secret rotation failed (event_type=secret_rotation_failed, "
            "message_id=%s, secret_id=%s, error=%s)",
            message_id,
            secret_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Rotation workflow failed: {type(e).__name__}",
        ) from e

    # Log completion
    logger.info(
        "Secret rotation completed (event_type=secret_rotation_completed, "
        "secret_name=%s, status=%s, version=%s, reason=%s, message_id=%s)",
        result.secret_name or "unknown",
        result.status,
        result.secret_version or "none",
        result.reason,
        message_id,
    )

    return JSONResponse(
        content={
            "status": result.status,
            "version": result.secret_version,
            "secret_name": result.secret_name,
        }
    )
