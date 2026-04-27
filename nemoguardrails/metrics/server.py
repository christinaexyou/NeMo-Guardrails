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

"""Server-specific metrics helpers (request tracking, config load counting).

These are thin wrappers around the library-wide instruments in
``nemoguardrails.metrics.instruments`` and the callback system in
``nemoguardrails.metrics.callbacks``.

Guardrails-specific metrics (rail activations, LLM calls, token usage) are
recorded inside ``LLMRails.generate_async`` when ``metrics.enabled`` is set
in config.yml, so they work regardless of whether the server is used.
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from nemoguardrails.metrics.callbacks import MetricsEvent, invoke_callbacks
from nemoguardrails.metrics.instruments import (
    config_load_counter,
    request_active,
    request_counter,
    request_duration,
)


@contextmanager
def track_request(config_id: str, streaming: bool = False):
    """Context manager that tracks HTTP-level request metrics.

    Records request count (with status), duration, and in-flight gauge.
    Also invokes any registered metrics callbacks on completion.

    Usage::

        with track_request(config_id="my_config") as tracker:
            result = await llm_rails.generate_async(...)
    """
    tracker = _RequestTracker(config_id, streaming)
    tracker._start()
    try:
        yield tracker
    except Exception:
        tracker.set_status("error")
        raise
    finally:
        tracker._finish()


class _RequestTracker:
    def __init__(self, config_id: str, streaming: bool = False):
        self._config_id = config_id
        self._streaming = streaming
        self._status = "success"
        self._start_time: float = 0.0

    def _start(self):
        self._start_time = time.perf_counter()
        request_active.add(1, {"config_id": self._config_id})

    def set_status(self, status: str) -> None:
        self._status = status

    def _finish(self):
        elapsed = time.perf_counter() - self._start_time

        attrs = {
            "config_id": self._config_id,
            "status": self._status,
            "streaming": self._streaming,
        }
        request_counter.add(1, attrs)
        request_duration.record(elapsed, {"config_id": self._config_id})
        request_active.add(-1, {"config_id": self._config_id})

        invoke_callbacks(
            MetricsEvent(
                config_id=self._config_id,
                status=self._status,
                duration=elapsed,
                streaming=self._streaming,
            )
        )


def record_config_load(config_id: str) -> None:
    """Record that a guardrails config was loaded."""
    config_load_counter.add(1, {"config_id": config_id})
