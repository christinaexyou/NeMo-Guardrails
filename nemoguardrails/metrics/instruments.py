# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

"""Shared OTel meter and built-in instruments for NeMo Guardrails.

These instruments can be used anywhere in the library — not just by the
server. All are no-ops unless a ``MeterProvider`` is configured by the
application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import metrics

if TYPE_CHECKING:
    from nemoguardrails.rails.llm.options import GenerationLog

# ---------------------------------------------------------------------------
# Shared meter
# ---------------------------------------------------------------------------

_meter = metrics.get_meter(
    "nemo_guardrails",
    schema_url="https://opentelemetry.io/schemas/1.26.0",
)

# ---------------------------------------------------------------------------
# Request-level instruments
# ---------------------------------------------------------------------------

request_counter = _meter.create_counter(
    name="guardrails.request.count",
    description="Total guardrails chat completion requests",
    unit="{request}",
)

request_duration = _meter.create_histogram(
    name="guardrails.request.duration",
    description="End-to-end guardrails request processing duration",
    unit="s",
)

request_active = _meter.create_up_down_counter(
    name="guardrails.request.active",
    description="Number of in-flight guardrails requests",
    unit="{request}",
)

# ---------------------------------------------------------------------------
# Rail instruments
# ---------------------------------------------------------------------------

rail_activated_counter = _meter.create_counter(
    name="guardrails.rail.activated",
    description="Number of times a rail was activated",
    unit="{activation}",
)

rail_blocked_counter = _meter.create_counter(
    name="guardrails.rail.blocked",
    description="Number of times a rail blocked a request",
    unit="{block}",
)

rail_duration = _meter.create_histogram(
    name="guardrails.rail.duration",
    description="Duration of individual rail execution",
    unit="s",
)

# ---------------------------------------------------------------------------
# LLM instruments
# ---------------------------------------------------------------------------

llm_call_counter = _meter.create_counter(
    name="guardrails.llm.call.count",
    description="Number of LLM calls made during guardrails processing",
    unit="{call}",
)

llm_call_duration = _meter.create_histogram(
    name="guardrails.llm.call.duration",
    description="Duration of individual LLM calls",
    unit="s",
)

llm_token_usage = _meter.create_histogram(
    name="guardrails.llm.token.usage",
    description="Token usage per LLM call",
    unit="{token}",
)

llm_cache_hit_counter = _meter.create_counter(
    name="guardrails.llm.cache.hit",
    description="Number of LLM calls served from cache",
    unit="{hit}",
)

# ---------------------------------------------------------------------------
# Config instruments
# ---------------------------------------------------------------------------

config_load_counter = _meter.create_counter(
    name="guardrails.config.load",
    description="Number of times a guardrails config was loaded",
    unit="{load}",
)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_meter() -> metrics.Meter:
    """Return the shared OpenTelemetry ``Meter`` for creating custom instruments.

    The returned meter produces no-op instruments unless the application has
    configured a real ``MeterProvider``::

        from nemoguardrails.metrics import get_meter

        meter = get_meter()
        my_hist = meter.create_histogram("myapp.latency", unit="s")
    """
    return _meter


def record_generation_log_metrics(gen_log: "GenerationLog", config_id: str) -> None:
    """Record metrics from activated rails and LLM calls in a GenerationLog.

    Can be called from any part of the library (server, LLMRails, etc.).
    """
    for rail in gen_log.activated_rails:
        rail_attrs = {
            "config_id": config_id,
            "rail_type": rail.type,
            "rail_name": rail.name,
        }
        rail_activated_counter.add(1, rail_attrs)

        if rail.stop:
            rail_blocked_counter.add(1, rail_attrs)

        if rail.duration is not None:
            rail_duration.record(rail.duration, rail_attrs)

        for action in rail.executed_actions:
            for llm_call in action.llm_calls:
                _record_llm_call(llm_call, config_id)

    if gen_log.llm_calls:
        for llm_call in gen_log.llm_calls:
            _record_llm_call(llm_call, config_id)


def _record_llm_call(llm_call, config_id: str) -> None:
    """Record metrics for a single LLM call."""
    call_attrs = {
        "config_id": config_id,
        "model": llm_call.llm_model_name or "unknown",
    }
    llm_call_counter.add(1, call_attrs)

    if getattr(llm_call, "from_cache", False):
        llm_cache_hit_counter.add(1, call_attrs)

    if llm_call.duration is not None:
        llm_call_duration.record(llm_call.duration, call_attrs)

    if llm_call.total_tokens is not None:
        llm_token_usage.record(llm_call.total_tokens, {**call_attrs, "token_type": "total"})
    if llm_call.prompt_tokens is not None:
        llm_token_usage.record(llm_call.prompt_tokens, {**call_attrs, "token_type": "prompt"})
    if llm_call.completion_tokens is not None:
        llm_token_usage.record(
            llm_call.completion_tokens,
            {**call_attrs, "token_type": "completion"},
        )
