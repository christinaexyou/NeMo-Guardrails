"""OpenTelemetry SDK configuration for the NeMo Guardrails server.

When the environment variable ``NEMO_GUARDRAILS_OTEL_SDK=true`` is set, this
module configures the full OTel SDK pipeline on server startup:

- **Traces** → exported via OTLP (gRPC) to the endpoint specified by
  ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default ``http://localhost:4317``).
- **Metrics** → exported via Prometheus (``/metrics`` on the server port)
  and optionally via OTLP if an endpoint is configured.
- **Logs** → Python ``logging`` records are bridged to the OTel Logs SDK and
  exported via OTLP.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

log = logging.getLogger(__name__)

_OTEL_SDK_ENV_VAR = "NEMO_GUARDRAILS_OTEL_SDK"

class _OTelInternalFilter(logging.Filter):
    _SUPPRESSED = ("opentelemetry", "grpc", "urllib3")
    def filter(self, record: logging.LogRecord) -> bool:
        return not any(record.name.startswith(ns) for ns in self._SUPPRESSED)

def is_otel_sdk_enabled() -> bool:
    """Return True when the built-in OTel SDK setup should be activated."""
    return os.getenv(_OTEL_SDK_ENV_VAR, "false").lower() in ("true", "1", "yes")


def configure_otel_sdk(
    service_name: Optional[str] = None,
) -> Optional[Callable[[], None]]:
    """Configure TracerProvider, MeterProvider, and LoggerProvider.

    Returns a ``shutdown()`` callable that flushes and shuts down all
    providers, or ``None`` if SDK packages are not installed.
    """
    try:
        from opentelemetry import metrics, trace
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        log.warning(
            "OTel SDK packages not installed (%s). "
            "Install with: pip install nemoguardrails[otel]",
            exc,
        )
        return None

    resolved_service_name = (
        service_name or os.getenv("OTEL_SERVICE_NAME") or "nemo-guardrails"
    )
    resource = Resource.create({SERVICE_NAME: resolved_service_name})

    # --- Traces ---
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    metric_readers = []

    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader

        prometheus_reader = PrometheusMetricReader()
        metric_readers.append(prometheus_reader)
    except ImportError:
        log.info(
            "PrometheusMetricReader not installed; "
            "Prometheus /metrics endpoint will not be available."
        )

    otlp_metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"
    )
    if otlp_metrics_endpoint:
        metric_readers.append(
            PeriodicExportingMetricReader(OTLPMetricExporter())
        )

    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)

    # --- Logs ---
    # Only enable the OTLP log bridge if the collector supports it.
    # Many collectors (e.g. those forwarding only to Tempo) don't have a
    # logs pipeline, which causes StatusCode.UNIMPLEMENTED errors.
    logger_provider = None
    if os.getenv("NEMO_GUARDRAILS_OTEL_LOGS", "false").lower() in ("true", "1", "yes"):
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter())
        )
        set_logger_provider(logger_provider)

        handler = LoggingHandler(
            level=logging.NOTSET, logger_provider=logger_provider
        )
        handler.addFilter(_OTelInternalFilter())
        logging.getLogger().addHandler(handler)

    logs_label = "OTLP" if logger_provider else "disabled"
    log.info(
        "OTel SDK configured: service=%s, traces=OTLP, metrics=%s, logs=%s",
        resolved_service_name,
        "Prometheus+OTLP" if otlp_metrics_endpoint else "Prometheus",
        logs_label,
    )

    def shutdown() -> None:
        providers = [tracer_provider, meter_provider]
        if logger_provider:
            providers.append(logger_provider)
        for provider in providers:
            try:
                provider.shutdown()
            except Exception:
                log.exception("Failed to shutdown OTel provider %s", provider)
        log.info("OTel SDK shutdown complete")

    return shutdown

def make_metrics_app():
    """Return a Prometheus ASGI app for mounting at ``/metrics``, or None.

    Uses ``prometheus_client.make_asgi_app()`` which serves the default
    registry — the same registry that ``PrometheusMetricReader`` writes to.
    """
    try:
        from prometheus_client import make_asgi_app

        return make_asgi_app()
    except ImportError:
        log.info(
            "prometheus_client not installed; /metrics endpoint unavailable."
        )
        return None
