#!/usr/bin/env python3
"""
OpenTelemetry-enabled entrypoint for NeMo Guardrails server.

This script sets up OpenTelemetry configuration before starting the NeMo Guardrails server
to ensure proper service name and tracing configuration.
"""

import os
import subprocess
import sys
from pathlib import Path


def setup_environment():
    """Set up environment variables for OpenTelemetry."""
    # Set default values if not provided
    os.environ.setdefault("OTEL_SERVICE_NAME", "guardrails")
    os.environ.setdefault("OTEL_SERVICE_VERSION", "1.0.0")
    os.environ.setdefault(
        "OTEL_RESOURCE_ATTRIBUTES", "deployment.environment=production"
    )
    os.environ.setdefault("OTEL_TRACES_EXPORTER", "console,otlp")
    os.environ.setdefault(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://host.docker.internal:4317"
    )
    os.environ.setdefault("OTEL_EXPORTER_OTLP_INSECURE", "true")


def main():
    """Main entrypoint that sets up OpenTelemetry and starts the server."""
    print("🔧 Setting up OpenTelemetry configuration...")

    # Set up environment
    setup_environment()

    # Add the config directory to Python path to import the otel setup
    config_id = os.environ.get("CONFIG_ID", "otel-adapter")
    config_dir = Path(f"/app/config/{config_id}")
    sys.path.insert(0, str(config_dir))

    # Import and setup OpenTelemetry (this must happen before NeMo Guardrails imports)
    try:
        from otel import setup_otel  # type: ignore  # noqa: F401

        setup_otel()
        service_name = os.environ.get("OTEL_SERVICE_NAME")
        print(f"✅ OpenTelemetry configured with service name: {service_name}")
    except ImportError as e:
        print(f"❌ Failed to import OpenTelemetry setup: {e}")
        print("   Make sure otel.py is in the configuration directory")
        sys.exit(1)
    except (RuntimeError, ValueError, ConnectionError) as e:
        print(f"❌ Failed to setup OpenTelemetry: {e}")
        sys.exit(1)

    # Get configuration from environment or defaults
    config_id = os.environ.get("CONFIG_ID", "otel-adapter")
    port = os.environ.get("PORT", "8000")

    print("🚀 Starting NeMo Guardrails server...")
    print(f"   - Config ID: {config_id}")
    print(f"   - Port: {port}")
    print(f"   - Service Name: {os.environ.get('OTEL_SERVICE_NAME')}")
    print(f"   - OTLP Endpoint: {os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT')}")

    # Validate config exists
    config_dir_path = f"/app/config/{config_id}"
    config_yaml = f"{config_dir_path}/config.yaml"
    rails_co = f"{config_dir_path}/rails.co"

    if not os.path.exists(config_yaml):
        print(f"❌ ERROR: config.yaml not found in {config_dir_path}")
        sys.exit(1)

    if not os.path.exists(rails_co):
        print(f"❌ ERROR: rails.co not found in {config_dir_path}")
        sys.exit(1)

    print("✅ Configuration validated. Starting server...")

    # Start the NeMo Guardrails server
    try:
        subprocess.run(
            [
                "/app/.venv/bin/nemoguardrails",
                "server",
                "--config",
                "/app/config",
                "--port",
                port,
                "--default-config-id",
                config_id,
                "--disable-chat-ui",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
