"""Tests for MLflow tracing integration via OpenTelemetry bridge."""

from unittest.mock import MagicMock, patch

import pytest

from lightspeed_agent.config import Settings
from lightspeed_agent.config.settings import get_settings


class TestMlflowSettingsDefaults:
    """Verify all MLflow settings have correct default values."""

    def test_mlflow_enabled_defaults_to_false(self):
        """mlflow_enabled defaults to False."""
        settings = Settings()
        assert settings.mlflow_enabled is False

    def test_mlflow_tracking_uri_default(self):
        """mlflow_tracking_uri defaults to http://localhost:5000."""
        settings = Settings()
        assert settings.mlflow_tracking_uri == "http://localhost:5000"

    def test_mlflow_experiment_name_default(self):
        """mlflow_experiment_name defaults to 'lightspeed-agent'."""
        settings = Settings()
        assert settings.mlflow_experiment_name == "lightspeed-agent"

    def test_mlflow_experiment_id_default(self):
        """mlflow_experiment_id defaults to empty string."""
        settings = Settings()
        assert settings.mlflow_experiment_id == ""

    def test_mlflow_log_prompts_defaults_to_false(self):
        """mlflow_log_prompts defaults to False."""
        settings = Settings()
        assert settings.mlflow_log_prompts is False

    def test_mlflow_run_tags_default(self):
        """mlflow_run_tags defaults to empty string."""
        settings = Settings()
        assert settings.mlflow_run_tags == ""

    def test_mlflow_tracking_token_default(self):
        """mlflow_tracking_token defaults to empty string."""
        settings = Settings()
        assert settings.mlflow_tracking_token == ""

    def test_mlflow_ca_bundle_default(self):
        """mlflow_ca_bundle defaults to empty string."""
        settings = Settings()
        assert settings.mlflow_ca_bundle == ""


class TestMlflowSettingsFromEnv:
    """Verify MLflow settings can be loaded from environment variables."""

    def test_mlflow_enabled_from_env(self, monkeypatch):
        """MLFLOW_ENABLED env var sets mlflow_enabled."""
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_enabled is True

    def test_mlflow_tracking_uri_from_env(self, monkeypatch):
        """MLFLOW_TRACKING_URI env var sets mlflow_tracking_uri."""
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.example.com:5000")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_tracking_uri == "http://mlflow.example.com:5000"

    def test_mlflow_experiment_name_from_env(self, monkeypatch):
        """MLFLOW_EXPERIMENT_NAME env var sets mlflow_experiment_name."""
        monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "my-experiment")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_experiment_name == "my-experiment"

    def test_mlflow_experiment_id_from_env(self, monkeypatch):
        """MLFLOW_EXPERIMENT_ID env var sets mlflow_experiment_id."""
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "42")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_experiment_id == "42"

    def test_mlflow_log_prompts_from_env(self, monkeypatch):
        """MLFLOW_LOG_PROMPTS env var sets mlflow_log_prompts."""
        monkeypatch.setenv("MLFLOW_LOG_PROMPTS", "true")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_log_prompts is True

    def test_mlflow_run_tags_from_env(self, monkeypatch):
        """MLFLOW_RUN_TAGS env var sets mlflow_run_tags."""
        monkeypatch.setenv("MLFLOW_RUN_TAGS", "env=prod,team=ai")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_run_tags == "env=prod,team=ai"

    def test_mlflow_tracking_token_from_env(self, monkeypatch):
        """MLFLOW_TRACKING_TOKEN env var sets mlflow_tracking_token."""
        monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "test-token-abc")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_tracking_token == "test-token-abc"

    def test_mlflow_ca_bundle_from_env(self, monkeypatch):
        """MLFLOW_CA_BUNDLE env var sets mlflow_ca_bundle."""
        monkeypatch.setenv("MLFLOW_CA_BUNDLE", "/path/to/ca.pem")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.mlflow_ca_bundle == "/path/to/ca.pem"


class TestMlflowDisabled:
    """Verify no MLflow exporter is added when mlflow_enabled=False."""

    def test_no_mlflow_processor_when_disabled(self, monkeypatch):
        """When mlflow_enabled=False, setup_telemetry adds no MLflow processor."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_TYPE", "console")
        monkeypatch.setenv("MLFLOW_ENABLED", "false")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        with (
            patch.object(telemetry_mod, "_instrument_fastapi"),
            patch.object(telemetry_mod, "_instrument_httpx"),
            patch(
                "opentelemetry.sdk.trace.TracerProvider.add_span_processor"
            ) as mock_add_processor,
        ):
            telemetry_mod.setup_telemetry()

            # Only one span processor: the primary exporter (console)
            assert mock_add_processor.call_count == 1

        # Cleanup
        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()

    def test_no_processors_when_both_disabled(self, monkeypatch):
        """When both otel_enabled=False and mlflow_enabled=False, no processors at all."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "false")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        with patch(
            "opentelemetry.sdk.trace.TracerProvider.add_span_processor"
        ) as mock_add_processor:
            telemetry_mod.setup_telemetry()
            mock_add_processor.assert_not_called()

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowIndependent:
    """Verify MLflow works independently of otel_enabled."""

    def test_mlflow_only_creates_provider_and_processor(self, monkeypatch):
        """When mlflow_enabled=True but otel_enabled=False, MLflow still gets a processor."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with (
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                mock_http_exporter_cls,
            ),
            patch(
                "opentelemetry.sdk.trace.TracerProvider.add_span_processor"
            ) as mock_add_processor,
        ):
            telemetry_mod.setup_telemetry()

            # Only MLflow processor (no OTel exporter since otel_enabled=False)
            assert mock_add_processor.call_count == 1
            mock_http_exporter_cls.assert_called_once()

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()

    def test_mlflow_only_no_fastapi_instrumentation(self, monkeypatch):
        """When only mlflow_enabled, FastAPI/HTTPX instrumentation is skipped."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        with (
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                MagicMock(),
            ),
            patch.object(telemetry_mod, "_instrument_fastapi") as mock_fastapi,
            patch.object(telemetry_mod, "_instrument_httpx") as mock_httpx,
        ):
            telemetry_mod.setup_telemetry()

            mock_fastapi.assert_not_called()
            mock_httpx.assert_not_called()

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowEnabled:
    """Verify MLflow exporter is added when mlflow_enabled=True."""

    def test_mlflow_processor_added_when_enabled(self, monkeypatch):
        """When mlflow_enabled=True, setup_telemetry adds a second BatchSpanProcessor."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_TYPE", "console")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()
        mock_http_exporter_instance = MagicMock()
        mock_http_exporter_cls.return_value = mock_http_exporter_instance

        with (
            patch.object(telemetry_mod, "_instrument_fastapi"),
            patch.object(telemetry_mod, "_instrument_httpx"),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                mock_http_exporter_cls,
            ),
            patch(
                "opentelemetry.sdk.trace.TracerProvider.add_span_processor"
            ) as mock_add_processor,
        ):
            telemetry_mod.setup_telemetry()

            # Two processors: primary exporter + MLflow exporter
            assert mock_add_processor.call_count == 2

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()

    def test_mlflow_exporter_targets_tracking_uri(self, monkeypatch):
        """MLflow OTLPSpanExporter is pointed at {tracking_uri}/v1/traces."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_TYPE", "console")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with (
            patch.object(telemetry_mod, "_instrument_fastapi"),
            patch.object(telemetry_mod, "_instrument_httpx"),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                mock_http_exporter_cls,
            ),
        ):
            telemetry_mod.setup_telemetry()

            mock_http_exporter_cls.assert_called_once()
            call_kwargs = mock_http_exporter_cls.call_args
            # Endpoint should be tracking_uri + /v1/traces
            endpoint = call_kwargs.kwargs.get(
                "endpoint", call_kwargs.args[0] if call_kwargs.args else None
            )
            assert endpoint == "http://mlflow.local:5000/v1/traces"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowExperimentIdHeader:
    """Verify x-mlflow-experiment-id header is passed when experiment_id is set."""

    def test_experiment_id_header_when_set(self, monkeypatch):
        """When mlflow_experiment_id is set, OTLPSpanExporter gets the header."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_TYPE", "console")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "42")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with (
            patch.object(telemetry_mod, "_instrument_fastapi"),
            patch.object(telemetry_mod, "_instrument_httpx"),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                mock_http_exporter_cls,
            ),
        ):
            telemetry_mod.setup_telemetry()

            mock_http_exporter_cls.assert_called_once()
            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "x-mlflow-experiment-id" in headers
            assert headers["x-mlflow-experiment-id"] == "42"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowNoExperimentId:
    """Verify error when no experiment ID can be resolved."""

    def test_raises_when_no_experiment_configured(self, monkeypatch):
        """When neither experiment ID nor name is set, raises RuntimeError."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        with (
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                MagicMock(),
            ),
            pytest.raises(RuntimeError, match="experiment ID could not be resolved"),
        ):
            telemetry_mod.setup_telemetry()

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowExperimentNameHeader:
    """Verify x-mlflow-experiment-name header is passed when experiment_name is set."""

    def test_experiment_name_header_when_set(self, monkeypatch):
        """When mlflow_experiment_name is set, OTLPSpanExporter gets the header."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "my-experiment")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert headers["x-mlflow-experiment-name"] == "my-experiment"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowLogPromptsHeader:
    """Verify x-mlflow-log-prompts header when log_prompts is enabled."""

    def test_log_prompts_header_when_true(self, monkeypatch):
        """When mlflow_log_prompts=True, header is sent."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_LOG_PROMPTS", "true")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert headers["x-mlflow-log-prompts"] == "true"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()

    def test_no_log_prompts_header_when_false(self, monkeypatch):
        """When mlflow_log_prompts=False, no header is sent."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_LOG_PROMPTS", "false")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "x-mlflow-log-prompts" not in headers

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowRunTagsHeader:
    """Verify x-mlflow-run-tags header when run_tags is set."""

    def test_run_tags_header_when_set(self, monkeypatch):
        """When mlflow_run_tags is set, header is sent."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_RUN_TAGS", "env=prod,team=ai")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert headers["x-mlflow-run-tags"] == "env=prod,team=ai"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowTrailingSlash:
    """Verify trailing slash in tracking_uri is stripped."""

    def test_trailing_slash_stripped(self, monkeypatch):
        """Trailing slash in tracking URI doesn't produce double-slash."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000/")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "0")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            endpoint = call_kwargs.kwargs.get(
                "endpoint", call_kwargs.args[0] if call_kwargs.args else None
            )
            assert endpoint == "http://mlflow.local:5000/v1/traces"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowAuthToken:
    """Verify Authorization header is passed when tracking token is set."""

    def test_auth_header_when_token_set(self, monkeypatch):
        """When mlflow_tracking_token is set, OTLPSpanExporter gets Authorization header."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "42")
        monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "my-secret-token")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert headers["Authorization"] == "Bearer my-secret-token"

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()

    def test_no_auth_header_when_token_empty(self, monkeypatch):
        """When mlflow_tracking_token is empty, no Authorization header."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", "42")
        monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        mock_http_exporter_cls = MagicMock()

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_http_exporter_cls,
        ):
            telemetry_mod.setup_telemetry()

            call_kwargs = mock_http_exporter_cls.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "Authorization" not in headers

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()


class TestMlflowExperimentResolutionAuth:
    """Verify token is passed in experiment resolution REST calls."""

    def test_resolve_passes_auth_header(self):
        """_resolve_mlflow_experiment_id sends Authorization header when token is set."""
        from lightspeed_agent.telemetry.setup import _resolve_mlflow_experiment_id

        response_body = b'{"experiment": {"experiment_id": "7"}}'

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = response_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = _resolve_mlflow_experiment_id(
                "http://mlflow.local:5000", "test-exp", token="my-token"
            )

            assert result == "7"
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            assert req.get_header("Authorization") == "Bearer my-token"

    def test_resolve_no_auth_header_when_empty_token(self):
        """_resolve_mlflow_experiment_id sends no Authorization header when token is empty."""
        from lightspeed_agent.telemetry.setup import _resolve_mlflow_experiment_id

        response_body = b'{"experiment": {"experiment_id": "7"}}'

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = response_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = _resolve_mlflow_experiment_id(
                "http://mlflow.local:5000", "test-exp", token=""
            )

            assert result == "7"
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            assert not req.has_header("Authorization")


class TestMlflowExperimentCreationDenied:
    """Verify clear error when managed instance denies experiment creation."""

    def test_403_on_create_raises_runtime_error(self):
        """A 403 on experiment create produces a clear RuntimeError."""
        import urllib.error

        from lightspeed_agent.telemetry.setup import _resolve_mlflow_experiment_id

        def side_effect(req, timeout=10, context=None):
            url = req.full_url if hasattr(req, "full_url") else req
            if "get-by-name" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

        with (
            patch("urllib.request.urlopen", side_effect=side_effect),
            pytest.raises(RuntimeError, match="Permission denied: cannot create experiment"),
        ):
            _resolve_mlflow_experiment_id(
                "http://mlflow.managed:5000", "nonexistent-exp", token="tok"
            )


class TestMlflowExperimentCreationSuccess:
    """Verify the 404-on-get -> create -> success path."""

    def test_404_then_create_returns_new_id(self):
        """When get-by-name returns 404, experiment is created and new ID returned."""
        import urllib.error

        from lightspeed_agent.telemetry.setup import _resolve_mlflow_experiment_id

        def side_effect(req, timeout=10, context=None):
            url = req.full_url if hasattr(req, "full_url") else req
            if "get-by-name" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            resp = MagicMock()
            resp.read.return_value = b'{"experiment_id": "42"}'
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=side_effect):
            result = _resolve_mlflow_experiment_id(
                "http://mlflow.local:5000", "new-experiment", token="tok"
            )

        assert result == "42"


class TestMlflowImportError:
    """Verify ImportError is handled when exporter package is missing."""

    def test_import_error_raises(self, monkeypatch):
        """When opentelemetry-exporter-otlp-proto-http is missing, ImportError is raised."""
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("MLFLOW_ENABLED", "true")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
        get_settings.cache_clear()

        import lightspeed_agent.telemetry.setup as telemetry_mod

        telemetry_mod._tracer_provider = None

        with (
            patch.dict(
                "sys.modules",
                {"opentelemetry.exporter.otlp.proto.http.trace_exporter": None},
            ),
            pytest.raises(ImportError),
        ):
            telemetry_mod.setup_telemetry()

        telemetry_mod._tracer_provider = None
        get_settings.cache_clear()
