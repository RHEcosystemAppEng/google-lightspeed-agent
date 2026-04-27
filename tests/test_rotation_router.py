"""Tests for rotation endpoint router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lightspeed_agent.rotation.workflow import RotationResult


@pytest.fixture
def mock_validator() -> AsyncMock:
    """Mock Pub/Sub JWT validator that always returns valid claims."""
    validator = AsyncMock()
    validator.validate_push_token.return_value = {
        "iss": "https://accounts.google.com",
        "aud": "https://test-agent.example.com",
    }
    return validator


@pytest.fixture
def mock_workflow() -> MagicMock:
    """Mock rotation workflow that returns success."""
    workflow = MagicMock()
    workflow.handle_event.return_value = RotationResult(
        status="rotated",
        reason="secret_version_added",
        secret_name="redhat-sso-client-secret",
        secret_version="projects/test-proj/secrets/redhat-sso-client-secret/versions/42",
    )
    return workflow


def test_rotation_endpoint_success(
    mock_validator: AsyncMock,
    mock_workflow: MagicMock,
) -> None:
    """Should handle valid rotation event and return 200."""
    from lightspeed_agent.rotation.router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Pub/Sub push message format
    request_body = {
        "message": {
            "messageId": "msg-123",
            "attributes": {
                "eventType": "SECRET_ROTATE",
                "secretId": "projects/test-proj/secrets/redhat-sso-client-secret",
            },
        },
        "subscription": "projects/test-proj/subscriptions/rotation-sub",
    }

    with patch(
        "lightspeed_agent.rotation.router.get_pubsub_jwt_validator",
        return_value=mock_validator,
    ), patch("lightspeed_agent.rotation.router._workflow", mock_workflow):
        response = client.post(
            "/rotation",
            json=request_body,
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert "versions/42" in data["version"]

    # Verify workflow was called with correct attributes
    mock_workflow.handle_event.assert_called_once()
    call_kwargs = mock_workflow.handle_event.call_args.kwargs
    assert call_kwargs["attributes"]["eventType"] == "SECRET_ROTATE"


def test_rotation_endpoint_missing_auth_header(mock_workflow: MagicMock) -> None:
    """Should return 401 when Authorization header is missing."""
    from lightspeed_agent.rotation.router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    request_body = {
        "message": {
            "messageId": "msg-123",
            "attributes": {"eventType": "SECRET_ROTATE"},
        }
    }

    response = client.post("/rotation", json=request_body)

    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]


def test_rotation_endpoint_invalid_token(mock_workflow: MagicMock) -> None:
    """Should return 401 when token validation fails."""
    from lightspeed_agent.rotation.router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    request_body = {
        "message": {
            "messageId": "msg-123",
            "attributes": {"eventType": "SECRET_ROTATE"},
        }
    }

    # Mock validator that rejects token
    invalid_validator = AsyncMock()
    invalid_validator.validate_push_token.return_value = None

    with patch(
        "lightspeed_agent.rotation.router.get_pubsub_jwt_validator",
        return_value=invalid_validator,
    ):
        response = client.post(
            "/rotation",
            json=request_body,
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert "Invalid Pub/Sub token" in response.json()["detail"]


def test_rotation_endpoint_missing_message(mock_validator: AsyncMock) -> None:
    """Should return 400 when message field is missing."""
    from lightspeed_agent.rotation.router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    request_body = {"subscription": "projects/test/subscriptions/sub"}

    with patch(
        "lightspeed_agent.rotation.router.get_pubsub_jwt_validator",
        return_value=mock_validator,
    ):
        response = client.post(
            "/rotation",
            json=request_body,
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 400
    assert "Missing Pub/Sub message" in response.json()["detail"]


def test_rotation_endpoint_workflow_failure(
    mock_validator: AsyncMock,
    mock_workflow: MagicMock,
) -> None:
    """Should return 500 when workflow raises exception."""
    from lightspeed_agent.rotation.router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    request_body = {
        "message": {
            "messageId": "msg-123",
            "attributes": {"eventType": "SECRET_ROTATE"},
        }
    }

    # Mock workflow that raises exception
    failing_workflow = MagicMock()
    failing_workflow.handle_event.side_effect = ValueError("Test error")

    with patch(
        "lightspeed_agent.rotation.router.get_pubsub_jwt_validator",
        return_value=mock_validator,
    ), patch("lightspeed_agent.rotation.router._workflow", failing_workflow):
        response = client.post(
            "/rotation",
            json=request_body,
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 500
    assert "Rotation workflow failed" in response.json()["detail"]


def test_rotation_endpoint_ignored_event(
    mock_validator: AsyncMock,
    mock_workflow: MagicMock,
) -> None:
    """Should return 200 for ignored events (unsupported secret)."""
    from lightspeed_agent.rotation.router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    request_body = {
        "message": {
            "messageId": "msg-123",
            "attributes": {
                "eventType": "SECRET_ROTATE",
                "secretId": "projects/test/secrets/unsupported-secret",
            },
        }
    }

    # Mock workflow that returns ignored status
    ignored_workflow = MagicMock()
    ignored_workflow.handle_event.return_value = RotationResult(
        status="ignored",
        reason="unsupported_secret",
        secret_name="unsupported-secret",
    )

    with patch(
        "lightspeed_agent.rotation.router.get_pubsub_jwt_validator",
        return_value=mock_validator,
    ), patch("lightspeed_agent.rotation.router._workflow", ignored_workflow):
        response = client.post(
            "/rotation",
            json=request_body,
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"


def test_rotation_router_integrated_in_marketplace_app() -> None:
    """Integration test: rotation router should be included in marketplace app.

    This test will FAIL until Task 5 integrates the rotation router into the
    marketplace app.
    """
    from lightspeed_agent.marketplace.app import create_app

    app = create_app()

    # Verify that /rotation endpoint is registered
    endpoints = [route.path for route in app.routes]
    assert "/rotation" in endpoints, f"Expected /rotation endpoint, found: {endpoints}"
