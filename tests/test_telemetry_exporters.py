"""Tests for supported telemetry exporter configuration and construction."""

import importlib
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from lightspeed_agent.config import Settings
from lightspeed_agent.telemetry.setup import _create_exporter


@pytest.mark.parametrize("exporter_type", ["otlp", "otlp-http", "zipkin", "console"])
def test_supported_exporter_configuration(exporter_type):
    settings = Settings(_env_file=None, otel_exporter_type=exporter_type)
    assert settings.otel_exporter_type == exporter_type


def test_native_jaeger_configuration_is_rejected():
    """Removed Jaeger settings must fail fast rather than silently use another exporter."""
    with pytest.raises(ValidationError, match="otel_exporter_type"):
        Settings(_env_file=None, otel_exporter_type="jaeger")


@pytest.mark.parametrize(
    "exporter_type,module_path,expected_endpoint",
    [
        (
            "otlp",
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
            "http://jaeger:4317",
        ),
        (
            "otlp-http",
            "opentelemetry.exporter.otlp.proto.http.trace_exporter",
            "http://jaeger:4318/v1/traces",
        ),
    ],
)
def test_jaeger_uses_otlp_exporter(monkeypatch, exporter_type, module_path, expected_endpoint):
    exporter_class = Mock()
    monkeypatch.setattr(importlib.import_module(module_path), "OTLPSpanExporter", exporter_class)

    exporter = _create_exporter(exporter_type, "http://jaeger:4317", "http://jaeger:4318")

    exporter_class.assert_called_once_with(endpoint=expected_endpoint)
    assert exporter is exporter_class.return_value


def test_zipkin_uses_json_exporter(monkeypatch):
    module = ModuleType("opentelemetry.exporter.zipkin.json")
    exporter_class = Mock()
    monkeypatch.setattr(module, "ZipkinExporter", exporter_class, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    exporter = _create_exporter("zipkin", "", "")

    exporter_class.assert_called_once_with()
    assert exporter is exporter_class.return_value


def test_missing_zipkin_exporter_recommends_json_package(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "opentelemetry.exporter.zipkin.json", None)

    with pytest.raises(ImportError):
        _create_exporter("zipkin", "", "")

    assert "pip install opentelemetry-exporter-zipkin-json" in caplog.text
