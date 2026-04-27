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

"""Metrics callback registry for custom post-request instrumentation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

log = logging.getLogger(__name__)

_metrics_callbacks: List[Callable[["MetricsEvent"], None]] = []


@dataclass
class MetricsEvent:
    """Context passed to registered metrics callbacks after each request."""

    config_id: str
    status: str
    duration: float
    streaming: bool
    response: Optional[Any] = field(default=None, repr=False)


def register_metrics_callback(callback: Callable[["MetricsEvent"], None]) -> None:
    """Register a callback invoked after every chat completion.

    The callback receives a ``MetricsEvent`` with request context. Combine
    with ``get_meter()`` to record custom metrics::

        from nemoguardrails.metrics import register_metrics_callback, get_meter

        meter = get_meter()
        special_counter = meter.create_counter("myapp.special")

        def on_completion(event):
            if event.status == "success":
                special_counter.add(1, {"config_id": event.config_id})

        register_metrics_callback(on_completion)
    """
    _metrics_callbacks.append(callback)


def invoke_callbacks(event: MetricsEvent) -> None:
    """Invoke all registered metrics callbacks."""
    for cb in _metrics_callbacks:
        try:
            cb(event)
        except Exception:
            # log error but continue
            log.exception("Error in metrics callback %s", cb)
