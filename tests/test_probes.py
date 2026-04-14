"""Tests for the health/readiness probe server."""

from fastapi.testclient import TestClient

from lightspeed_agent.probes.server import create_probe_app


class TestProbeEndpoints:
    """Tests for probe app health and readiness endpoints."""

    def test_health_endpoint_returns_200(self):
        """Test GET /health returns 200 with healthy status."""
        app = create_probe_app(service_name="test-agent")
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_ready_endpoint_returns_200(self):
        """Test GET /ready returns 200 with ready status."""
        app = create_probe_app(service_name="test-agent")
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_health_endpoint_includes_service_name(self):
        """Test that the service name passed to create_probe_app appears in /health response."""
        app = create_probe_app(service_name="my-custom-service")
        client = TestClient(app)

        response = client.get("/health")

        data = response.json()
        assert data["service"] == "my-custom-service"

    def test_ready_endpoint_includes_service_name(self):
        """Test that the service name passed to create_probe_app appears in /ready response."""
        app = create_probe_app(service_name="my-custom-service")
        client = TestClient(app)

        response = client.get("/ready")

        data = response.json()
        assert data["service"] == "my-custom-service"

    def test_probe_app_has_no_other_routes(self):
        """Test that GET to a random path returns 404 (no unexpected routes)."""
        app = create_probe_app(service_name="test-agent")
        client = TestClient(app)

        response = client.get("/nonexistent")

        assert response.status_code == 404

    def test_probe_app_different_service_names(self):
        """Test that different service names produce correct responses."""
        app_a = create_probe_app(service_name="agent-service")
        app_b = create_probe_app(service_name="marketplace-service")
        client_a = TestClient(app_a)
        client_b = TestClient(app_b)

        health_a = client_a.get("/health").json()
        health_b = client_b.get("/health").json()

        assert health_a["service"] == "agent-service"
        assert health_b["service"] == "marketplace-service"
        assert health_a["service"] != health_b["service"]
