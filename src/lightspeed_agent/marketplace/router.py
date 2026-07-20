"""Marketplace Handler Router.

Implements separate endpoints for:
1. /dcr — Direct DCR requests from Gemini Enterprise (contains software_statement)
2. /pubsub — Pub/Sub events from Google Cloud Marketplace, verified via Google OIDC

Pub/Sub push messages are authenticated by verifying the Google-signed OIDC token
in the Authorization header before processing any event.
"""

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from lightspeed_agent.config import Settings, get_settings
from lightspeed_agent.dcr import DCRError, DCRRequest, get_dcr_service
from lightspeed_agent.marketplace.models import ProcurementEvent, ProcurementEventType
from lightspeed_agent.marketplace.service import get_procurement_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Marketplace Handler"])


@router.post("/dcr")
async def dcr_handler(request: Request) -> JSONResponse:
    """Handle DCR (Dynamic Client Registration) requests from Gemini Enterprise.

    Accepts requests containing a `software_statement` JWT. Pub/Sub messages
    must be sent to the /pubsub endpoint instead.

    Returns:
        DCR credentials or error.
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    if "software_statement" not in body:
        raise HTTPException(
            status_code=400,
            detail="Request must contain 'software_statement'. "
            "Pub/Sub events should be sent to /pubsub.",
        )

    return await _handle_dcr_request(body)


@router.post("/pubsub")
async def pubsub_handler(request: Request) -> JSONResponse:
    """Handle Pub/Sub events from Google Cloud Marketplace.

    Verifies the Google-signed OIDC token in the Authorization header
    before processing any event. Rejects unauthenticated requests.

    Returns:
        Acknowledgment or error.
    """
    settings = get_settings()

    # Verify Google OIDC token (skipped in standalone/dev deployments)
    if not settings.skip_pubsub_oidc_verification:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header. "
                "Pub/Sub push subscriptions must be configured with OIDC authentication.",
            )

        token = auth_header[7:]

        try:
            audience = settings.pubsub_audience or None
            await asyncio.to_thread(
                google_id_token.verify_oauth2_token,
                token,
                google_requests.Request(),
                audience=audience,
            )
        except (ValueError, google_auth_exceptions.GoogleAuthError) as e:
            logger.warning("Pub/Sub OIDC token verification failed: %s", e)
            raise HTTPException(
                status_code=401,
                detail="Invalid Pub/Sub OIDC token",
            ) from e

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    if "message" not in body:
        raise HTTPException(
            status_code=400,
            detail="Request must contain 'message' with Pub/Sub payload.",
        )

    return await _handle_pubsub_event(body)


async def _handle_dcr_request(body: dict[str, Any]) -> JSONResponse:
    """Handle a direct DCR request from Gemini Enterprise.

    Args:
        body: Request body containing software_statement.

    Returns:
        JSONResponse with client credentials or error.
    """
    logger.info("Processing DCR request")

    dcr_service = get_dcr_service()
    dcr_request = DCRRequest(
        software_statement=body["software_statement"],
    )

    result = await dcr_service.register_client(dcr_request)

    if isinstance(result, DCRError):
        logger.warning("DCR error: %s - %s", result.error, result.error_description)
        return JSONResponse(
            status_code=400,
            content={
                "error": result.error.value,
                "error_description": result.error_description,
            },
            headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Expires": "0"},
        )

    logger.info("DCR successful: client_id=%s", result.client_id)
    return JSONResponse(
        status_code=201,
        content={
            "client_id": result.client_id,
            "client_secret": result.client_secret,
            "client_secret_expires_at": result.client_secret_expires_at,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Expires": "0"},
    )


async def _handle_pubsub_event(body: dict[str, Any]) -> JSONResponse:
    """Handle a Pub/Sub event from Google Cloud Marketplace.

    Args:
        body: Request body containing Pub/Sub message.

    Returns:
        JSONResponse acknowledging the event.
    """
    message = body.get("message", {})
    message_id = message.get("messageId", "unknown")

    logger.info("Processing Pub/Sub message: %s", message_id)

    # Decode the message data
    data_b64 = message.get("data", "")
    if not data_b64:
        logger.warning("Empty Pub/Sub message data")
        return JSONResponse(content={"status": "ok", "message": "Empty message"})

    try:
        data_json = base64.b64decode(data_b64).decode("utf-8")
        data = json.loads(data_json)
    except Exception as e:
        logger.error("Failed to decode Pub/Sub message: %s", e)
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid message encoding"},
        )

    # Extract event type and process
    event_type_str = data.get("eventType", "")
    logger.info("Marketplace event type: %s", event_type_str)

    # Product-level filtering: in multi-agent deployments, a single Pub/Sub
    # topic is shared across all agents in the same project. Filter events
    # by product to ensure each agent only processes its own entitlements.
    settings = get_settings()
    entitlement_data = data.get("entitlement")
    product = entitlement_data.get("product") if entitlement_data else None

    # GCP Pub/Sub notifications often omit the product field. When filtering
    # is configured, fetch it from the Procurement API if missing.
    if not product and settings.service_control_service_name and entitlement_data:
        entitlement_id = (
            entitlement_data.get("id")
            or entitlement_data.get("name", "").split("/")[-1]
        )
        if entitlement_id:
            product = await _fetch_entitlement_product(entitlement_id, settings)

    if product == _NOT_AUTHORIZED:
        logger.warning(
            "Entitlement %s skipped: SA returned 403 from Procurement API "
            "(different product, or SA not registered in Producer Portal)",
            entitlement_data.get("id", "unknown") if entitlement_data else "unknown",
        )
        return JSONResponse(content={"status": "ok", "message": "not for this product"})

    # Fail-closed: when filtering is configured but product can't be determined,
    # skip the event. Pub/Sub will retry on transient API failures.
    if not product and settings.service_control_service_name and entitlement_data:
        logger.warning(
            "Could not determine product for entitlement %s — skipping (fail-closed)",
            entitlement_data.get("id", "unknown"),
        )
        return JSONResponse(
            content={"status": "ok", "message": "Product could not be determined, skipping"},
        )

    if product and settings.service_control_service_name:
        product_id = product.removeprefix("products/")
        if product_id != settings.service_control_service_name:
            logger.info(
                "Skipping event for different product: %s (expected %s)",
                product_id,
                settings.service_control_service_name,
            )
            return JSONResponse(content={"status": "ok", "message": "Event not for this product"})

    # Try to parse as a known event type
    try:
        event_type = ProcurementEventType(event_type_str)
    except ValueError:
        logger.warning("Unknown event type: %s", event_type_str)
        return JSONResponse(content={"status": "ok", "message": f"Unknown event: {event_type_str}"})

    # Build procurement event
    event = _build_procurement_event(data, event_type)
    if not event:
        logger.warning("Could not build procurement event from data")
        return JSONResponse(content={"status": "ok", "message": "Invalid event data"})

    # Process the event — let failures propagate as 500 so Pub/Sub retries.
    procurement_service = get_procurement_service()
    try:
        await procurement_service.process_event(event)
    except Exception as e:
        logger.exception("Failed to process marketplace event %s: %s", message_id, e)
        return JSONResponse(
            status_code=500,
            content={
                "error": "event_processing_failed",
                "message": "Internal error processing event",
            },
        )

    order_id = event.entitlement.id if event.entitlement else None
    logger.info("Processed marketplace event: %s (%s)", message_id, event_type_str)
    return JSONResponse(content={"status": "success", "orderId": order_id})


def _build_procurement_event(
    data: dict[str, Any],
    event_type: ProcurementEventType,
) -> ProcurementEvent | None:
    """Build a ProcurementEvent from Pub/Sub message data.

    Args:
        data: Decoded message data.
        event_type: The event type.

    Returns:
        ProcurementEvent or None if invalid.
    """
    from lightspeed_agent.marketplace.models import (
        AccountInfo,
        EntitlementInfo,
        ProcurementEvent,
    )

    settings = get_settings()

    # Extract common fields
    event_id = data.get("eventId", data.get("id", "unknown"))
    provider_id = data.get("providerId", settings.service_control_service_name or "")

    # Extract account info (multiple possible locations)
    account_data = data.get("account", {})
    account_id = (
        account_data.get("id")
        or account_data.get("name", "").split("/")[-1]
        or data.get("accountId")
        or data.get("account_id")
    )

    account_info = None
    if account_id:
        account_info = AccountInfo(
            id=account_id,
            updateTime=account_data.get("updateTime"),
        )

    # Extract entitlement info (multiple possible locations)
    entitlement_data = data.get("entitlement", {})
    entitlement_id = (
        entitlement_data.get("id")
        or entitlement_data.get("name", "").split("/")[-1]
        or data.get("entitlementId")
        or data.get("entitlement_id")
        or data.get("orderId")
        or data.get("order_id")
    )

    entitlement_info = None
    if entitlement_id:
        entitlement_info = EntitlementInfo(
            id=entitlement_id,
            newPlan=entitlement_data.get("newPlan") or entitlement_data.get("plan"),
            previousPlan=entitlement_data.get("previousPlan"),
            product=entitlement_data.get("product"),
            newOfferStartTime=entitlement_data.get("newOfferStartTime"),
            newOfferEndTime=entitlement_data.get("newOfferEndTime"),
            cancellationReason=entitlement_data.get("cancellationReason"),
            updateTime=entitlement_data.get("updateTime"),
        )

    return ProcurementEvent(
        eventId=event_id,
        eventType=event_type,
        providerId=provider_id,
        account=account_info,
        entitlement=entitlement_info,
    )


_NOT_AUTHORIZED = "__not_authorized__"


async def _fetch_entitlement_product(entitlement_id: str, settings: Settings) -> str | None:
    """Fetch the product field for an entitlement from the Procurement API.

    Used for product-level filtering when the Pub/Sub message doesn't include
    the product field (which is common for most event types).

    Returns the product string, _NOT_AUTHORIZED if the SA lacks permission
    (meaning this entitlement belongs to a different product), or None if
    the product could not be determined.
    """
    import google.auth
    import httpx

    project = settings.google_cloud_project
    if not project:
        return None

    url = (
        f"https://cloudcommerceprocurement.googleapis.com/v1"
        f"/providers/{project}/entitlements/{entitlement_id}"
    )

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        await asyncio.to_thread(credentials.refresh, google_requests.Request())
        headers = {"Authorization": f"Bearer {credentials.token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)

        if response.status_code == 200:
            product: str = response.json().get("product", "")
            if product:
                logger.info(
                    "Resolved product %s for entitlement %s via API",
                    product,
                    entitlement_id,
                )
                return product
        elif response.status_code == 403:
            logger.warning(
                "403 fetching entitlement %s — either belongs to a different product "
                "or this SA is not registered in the Producer Portal Technical Integration",
                entitlement_id,
            )
            return _NOT_AUTHORIZED
        else:
            logger.warning(
                "Could not fetch entitlement %s for product filtering (HTTP %d)",
                entitlement_id,
                response.status_code,
            )
    except Exception as e:
        logger.warning("Error fetching entitlement %s for product filtering: %s", entitlement_id, e)

    return None
