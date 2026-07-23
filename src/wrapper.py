"""Small Gemini transport wrapper used by the stable backend."""

from pydantic import BaseModel
import httpx
import logging

from typing import final
import asyncio

from .schema import CharacterConfig, Settings

MAX_TOKENS = 500
DELAY = 1
DELIMITER = "\n----------\n"
logger = logging.getLogger(__name__)


class APIFailureError(Exception):
    """Legacy compatibility exception kept for callers that import it."""
    pass


@final
class GeminiWrapper:
    def __init__(self, base_url: str, api_keys: list[str], model: str, timeout: int):
        # The wrapper keeps one shared HTTP client and rotates keys on 429.
        self.model = model
        self.api_keys = api_keys
        self.key_index = 0
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout
        )
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings):
        """Create the wrapper from environment-backed application settings."""
        return GeminiWrapper(settings.base_url, settings.api_keys, settings.model, 30)

    async def _generate[T: BaseModel](
        self,
        config: CharacterConfig[T],
        prompt: str,
        timeout: int
    ) -> httpx.Response:
        """Send one structured-generation request to Gemini."""
        data = {
            "systemInstruction": {
                "parts": [{
                    "text": config.system_instruction + DELIMITER + config.prompt,
                }],
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": config.schema.model_json_schema(),
                "temperature": 0,
                "maxOutputTokens": MAX_TOKENS,
                "thinkingConfig": {"thinkingBudget": 0},
            },
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}],
            }],
        }
        response = await self.client.post(
            f"models/{self.model}:generateContent",
            timeout=timeout,
            headers={"x-goog-api-key": self.api_keys[self.key_index]},
            json=data,
        )

        return response

    async def generate[T: BaseModel](
        self,
        config: CharacterConfig[T],
        prompt: str
    ) -> T:
        """Retry a structured generation call and rotate API keys on rate limits."""
        time_taken: int = 0
        for i in range(3):
            resp = await self._generate(config, prompt, self.timeout - time_taken)

            if resp.status_code == 200:
                payload: dict = resp.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                return config.schema.model_validate_json(text)
            elif resp.status_code == 429:
                logger.warning(
                    "Gemini API rate limit reached for API key index %d",
                    self.key_index,
                )
                self.key_index = (self.key_index + 1) % len(self.api_keys)
                await asyncio.sleep(DELAY * (2 ** i))

            if i == 2 or resp.elapsed.total_seconds() > self.timeout:
                _ = resp.raise_for_status()

            time_taken += resp.elapsed.total_seconds() + DELAY * (2 ** i)

        raise httpx.HTTPError("Unreachable")

    async def close(self):
        """Close the shared async HTTP client during app shutdown."""
        return await self.client.aclose()
