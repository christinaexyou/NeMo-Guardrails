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

import logging
import os
from typing import Dict, Optional, Union

from langchain_core.language_models import BaseChatModel, BaseLLM

from nemoguardrails.llm.cache import CacheInterface, LFUCache
from nemoguardrails.llm.models.initializer import (
    ModelInitializationError,
    init_llm_model,
)
from nemoguardrails.rails.llm.config import InvalidModelConfigurationError, RailsConfig

log = logging.getLogger(__name__)


class ModelFactory:
    def __init__(
        self,
        config: RailsConfig,
        llm: Optional[Union[BaseLLM, BaseChatModel]] = None,
    ):
        """
        Initializes the ModelFactory instance.
        """

        self.config = config
        self.llm = llm

    def _init_llms(self):
        """
        Initializes the right LLM engines based on the configuration.
        There can be multiple LLM engines and types that can be specified in the config.
        The main LLM engine is the one that will be used for all the core guardrails generations.
        Other LLM engines can be specified for use in specific actions.

        The reason we provide an option for decoupling the main LLM engine from the action LLM
        is to allow for flexibility in using specialized LLM engines for specific actions.

        Raises:
            ModelInitializationError: If any model initialization fails
        """

        if self.llm:
            # If an LLM was provided via constructor, use it as the main LLM
            # Log a warning if a main LLM is also specified in the config
            if any(model.type == "main" for model in self.config.models):
                log.warning(
                    "Both an LLM was provided via constructor and a main LLM is specified in the config. "
                    "The LLM provided via constructor will be used and the main LLM from config will be ignored."
                )

        else:
            # Otherwise, initialize the main LLM from the config
            main_model = next((model for model in self.config.models if model.type == "main"), None)

            if main_model and main_model.model:
                kwargs = self._prepare_model_kwargs(main_model)
                self.llm = init_llm_model(
                    model_name=main_model.model,
                    provider_name=main_model.engine,
                    mode="chat",
                    kwargs=kwargs,
                )
            else:
                log.warning("No main LLM specified in the config and no LLM provided via constructor.")

        llms = dict()

        for llm_config in self.config.models:
            if llm_config.type in ["embeddings", "jailbreak_detection"]:
                continue

            # If a constructor LLM is provided, skip initializing any 'main' model from config
            if self.llm and llm_config.type == "main":
                continue

            try:
                model_name = llm_config.model
                if not model_name:
                    raise InvalidModelConfigurationError(
                        f"`model` field must be set in model configuration: {llm_config.model_dump_json()}"
                    )

                provider_name = llm_config.engine
                kwargs = self._prepare_model_kwargs(llm_config)
                mode = llm_config.mode

                llm_model = init_llm_model(
                    model_name=model_name,
                    provider_name=provider_name,
                    mode=mode,
                    kwargs=kwargs,
                )

                # Configure the model based on its type
                if llm_config.type == "main":
                    # If a main LLM was already injected, skip creating another
                    # one. Otherwise, create and register it.
                    if not self.llm:
                        self.llm = llm_model
                else:
                    model_name = f"{llm_config.type}_llm"
                    if not hasattr(self, model_name):
                        setattr(self, model_name, llm_model)

                    # this is used for content safety and topic control
                    llms[llm_config.type] = getattr(self, model_name)

            except ModelInitializationError as e:
                log.error("Failed to initialize model: %s", str(e))
                raise
            except Exception as e:
                log.error("Unexpected error initializing model: %s", str(e))
                raise

        model_caches = self._initialize_model_caches()

        return self.llm, llms, model_caches

    def _prepare_model_kwargs(self, model_config):
        """
        Prepare kwargs for model initialization, including API key from environment variable.

        Args:
            model_config: The model configuration object

        Returns:
            dict: The prepared kwargs for model initialization
        """
        kwargs = model_config.parameters or {}

        # If the optional API Key Environment Variable is set, add it to kwargs
        if model_config.api_key_env_var:
            api_key = os.environ.get(model_config.api_key_env_var)
            if api_key:
                kwargs["api_key"] = api_key

        # enable streaming token usage
        # providers that don't support this parameter will simply ignore it
        kwargs["stream_usage"] = True

        return kwargs

    def _initialize_model_caches(self):
        """
        Initializes the model caches based on the configuration.
        """
        model_caches: Optional[Dict[str, CacheInterface]] = dict()
        for model in self.config.models:
            if model.type in ["main", "embeddings"]:
                continue

            if model.cache and model.cache.enabled:
                cache = self._create_model_cache(model)
                model_caches[model.type] = cache

                log.info(
                    f"Initialized model '{model.type}' with cache %s",
                    "enabled" if cache else "disabled",
                )
        return model_caches

    def _create_model_cache(self, model) -> LFUCache:
        """
        Create cache instance for a model based on its configuration.

        Args:
            model: The model configuration object

        Returns:
            LFUCache: The cache instance
        """
        if model.cache.maxsize <= 0:
            raise ValueError(
                f"Invalid cache maxsize for model '{model.type}': {model.cache.maxsize}. "
                "Capacity must be greater than 0. Skipping cache creation."
            )

        stats_logging_interval = None
        if model.cache.stats.enabled and model.cache.stats.log_interval is not None:
            stats_logging_interval = model.cache.stats.log_interval

        cache = LFUCache(
            maxsize=model.cache.maxsize,
            track_stats=model.cache.stats.enabled,
            stats_logging_interval=stats_logging_interval,
        )

        log.info(f"Created cache for model '{model.type}' with maxsize {model.cache.maxsize}")

        return cache

    def _configure_main_llm_streaming(
        self,
        llm: Union[BaseLLM, BaseChatModel],
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
    ):
        """
        Configure streaming support for the main LLM.

        Args:
            llm (Union[BaseLLM, BaseChatModel]): The main LLM model instance.
            model_name (Optional[str], optional): Optional model name for logging.
            provider_name (Optional[str], optional): Optional provider name for logging.

        """
        if hasattr(llm, "streaming"):
            setattr(llm, "streaming", True)
