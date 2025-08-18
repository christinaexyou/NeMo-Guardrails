import logging
import os
from typing import List, Optional

import aiohttp

from nemoguardrails import RailsConfig
from nemoguardrails.actions import action
from nemoguardrails.rails.llm.config import KServeDetectorConfig

log = logging.getLogger(__name__)
# HuggingFace input format
# ================================
# [
#   [
#     {
#       "start": 0,
#       "end": 36,
#       "text": "You dotard, I really hate this stuff",
#       "detection": "single_label_classification",
#       "detection_type": "LABEL_1",
#       "score": 0.9634233713150024,
#       "evidences": []
#     }
#   ],
#   []
# ]

# LLM as a Judge input format
# ================================
# [
#     {
#       "start": 0,
#       "end": 36,
#       "text": "You dotard, I really hate this stuff",
#       "detection": "UNSAFE",
#       "detection_type": "llm_judge",
#       "score": 0.2,
#       "evidences": [],
#       "metadata": {
#         "reasoning": "The content contains a derogatory term and expresses strong negative emotions, which could potentially cause psychological harm or social conflict. It does not pose physical or legal risks but the emotional tone could be harmful."
#       }
#     }
#   ],


async def call_kserve_detector(
    endpoint: str,
    contents: List[str],
    detector_id,
    detector_params,
):
    api_token = os.environ.get("KSERVE_API_TOKEN")

    if api_token is None:
        raise ValueError("KSERVE_API_TOKEN environment variable not set.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                headers=headers,
                json={"contents": contents, "detector_params": detector_params},
            ) as response:
                if response.status != 200:
                    log.error(
                        f"{detector_id} could not be run. KServe API returned status code {response.status}"
                    )
                    return False

                response_json = await response.json()
                return response_json.get("score")

    except aiohttp.ClientError as e:
        log.error(f"{detector_id} request failed: {e}")
        return False
    except (KeyError, ValueError, IndexError) as e:
        log.error(f"Error processing {detector_id} response: {e}")
        return False


def kserve_output_mapping(result: dict) -> bool:
    score = result.get("score", 0)
    return score > 0.5
