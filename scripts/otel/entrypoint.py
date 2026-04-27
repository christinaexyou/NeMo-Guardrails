#!/usr/bin/env python
"""Entrypoint that optionally bootstraps the OTel SDK before starting the server."""

import argparse
import logging
import os

import uvicorn

logging.basicConfig(level=logging.INFO)

from scripts.otel.otel import configure_otel_sdk, is_otel_sdk_enabled, make_metrics_app

_SHUTDOWN = None
if is_otel_sdk_enabled():
    _SHUTDOWN = configure_otel_sdk()

try:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("CONFIG_DIR", "config"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--default-config-id", default=os.environ.get("CONFIG_ID"))
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--disable-chat-ui", action="store_true", default=True)
    args = parser.parse_args()

    from nemoguardrails.server.api import app

    app.rails_config_path = os.path.abspath(args.config)
    if args.default_config_id:
        app.default_config_id = args.default_config_id
    app.disable_chat_ui = args.disable_chat_ui

    if is_otel_sdk_enabled():
        metrics_app = make_metrics_app()
        if metrics_app:
            app.mount("/metrics/", metrics_app)

    log_level = "debug" if args.verbose else "info"
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level=log_level)
finally:
    if _SHUTDOWN:
        _SHUTDOWN()
