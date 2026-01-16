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
from typing import Callable, Optional

from nemoguardrails.embeddings.index import EmbeddingsIndex
from nemoguardrails.kb.kb import KnowledgeBase
from nemoguardrails.rails.llm.config import EmbeddingSearchProvider, RailsConfig

log = logging.getLogger(__name__)


class KnowledgeBaseBuilder:
    def __init__(
        self,
        config: RailsConfig,
        get_embeddings_search_provider_instance: Callable[[Optional[EmbeddingSearchProvider]], EmbeddingsIndex],
    ):
        """Initializes the knowledge base."""
        self.kb = None
        self.config = config
        self.get_embeddings_search_provider_instance = get_embeddings_search_provider_instance

    async def build(self):
        """Build the knowledge base from the configuration."""
        if not self.config.docs:
            return

        documents = [doc.content for doc in self.config.docs]
        self.kb = KnowledgeBase(
            documents=documents,
            config=self.config.knowledge_base,
            get_embedding_search_provider_instance=self.get_embeddings_search_provider_instance,
        )
        self.kb.init()
        await self.kb.build()

    def get_kb(self) -> Optional[KnowledgeBase]:
        """Get the knowledge base instance."""
        return self.kb
