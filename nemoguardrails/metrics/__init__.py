# SPDX-FileCopyrightText: Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""OpenTelemetry Metrics instrumentation for NeMo Guardrails.

Uses only the OpenTelemetry Metrics API (no SDK). All instruments are no-ops
unless the application configures a ``MeterProvider``.

To export to Prometheus, configure the SDK in your application code::

    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.exporter.prometheus import PrometheusMetricReader

    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)

Custom metrics
--------------

Use ``get_meter()`` to obtain the shared ``Meter`` and create your own
instruments::

    from nemoguardrails.metrics import get_meter

    meter = get_meter()
    my_counter = meter.create_counter("myapp.custom.count")
    my_counter.add(1, {"label": "value"})

Or register a callback invoked after every chat completion::

    from nemoguardrails.metrics import register_metrics_callback

    def on_completion(event):
        # event is a MetricsEvent with config_id, status, duration,
        # streaming flag, and the GenerationResponse (if available).
        ...

    register_metrics_callback(on_completion)
"""

from nemoguardrails.metrics.callbacks import (
    MetricsEvent,
    register_metrics_callback,
)
from nemoguardrails.metrics.instruments import (
    get_meter,
    record_generation_log_metrics,
)

__all__ = [
    "MetricsEvent",
    "get_meter",
    "record_generation_log_metrics",
    "register_metrics_callback",
]
