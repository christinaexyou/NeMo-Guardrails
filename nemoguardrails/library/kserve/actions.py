import logging
import os
from typing import List

import aiohttp
from pydantic import BaseModel, Field

from nemoguardrails import RailsConfig
from nemoguardrails.actions import action
from nemoguardrails.rails.llm.config import KServeDetectorConfig

log = logging.getLogger(__name__)


async def call_kserve_detector(
    endpoint: str,
    content: dict,
    detector_id: str,
) -> bool:
    api_key = os.getenv("KSERVE_API_KEY")
    if not api_key:
        raise ValueError("KSERVE_API_KEY environment variable is not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                # TODO: configurable at runtime or deployment time?
                endpoint,
                headers=headers,
                json={"content": content},
            ) as response:
                if response.status != 200:
                    log.error(
                        f"f{detector_id} could not be run. KServe API returned status code {response.status}"
                    )
                    return False

            response_json = await response.json()[0][0]
            # check if response contains valid detection type
            # get detection score from response
            detection_score = get_kserve_detector_output_mapping(response_json)
    except aiohttp.ClientError as e:
        log.error(f"{dectector_id} request failed: {e}")
        return False
    except (KeyError, ValueError, IndexError) as e:
        log.error(f"Error parsing {detector_id} response: {e}")
        return False


def get_kserve_detector_output_mapping(result):
    score = result.get("score")
    return score > 0.6


@action("call kserve hf detector", is_system_action=True)
async def call_kserve_hf_detector(
    config: RailsConfig, context: dict, detector_params: dict = None
):
    kserve_config: KServeDetectorConfig = getattr(
        config.rails.config, "kserve_detector"
    )

    inference_endpoint = kserve_config.inference_endpoint
    if inference_endpoint is None:
        raise ValueError("KServe inference endpoint is not set in the configuration")

    messages = context.get("user_input", "")
    detector_params = detector_params or context.get("detector_params", {})

    if len(messages) == 0:
        log.error("KServe Detectors could not be run. Text contents must be provided.")

    payload = {"contents": messages, "dectector_params": detector_params}

    return await call_kserve_detector(
        endpoint=inference_endpoint,
        content=payload,
        detector_id=kserve_config.detector_id,
    )
