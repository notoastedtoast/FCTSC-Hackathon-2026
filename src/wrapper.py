from pydantic import BaseModel
from collections import OrderedDict
from collections.abc import Hashable
import httpx
import logging

from typing import cast, final
import asyncio
from time import monotonic

from .schema import CharacterConfig, Settings

DELAY = 1
DELIMITER = "\n----------\n"
logger = logging.getLogger(__name__)


@final
class LRUCache[T]:
    """Small in-memory LRU cache with TTL-based expiry."""

    def __init__(self, maxsize: int = 128, ttl: float = 300) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._items: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()

    def get(self, key: Hashable) -> T | None:
        item = self._items.pop(key, None)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= monotonic():
            return None
        self._items[key] = item
        return value

    def set(self, key: Hashable, value: T) -> None:
        _ = self._items.pop(key, None)
        self._items[key] = (monotonic() + self.ttl, value)
        while len(self._items) > self.maxsize:
            _ = self._items.popitem(last=False)


@final
class GeminiWrapper:
    def __init__(self, base_url: str, api_keys: list[str], model: str, timeout: float):
        self.model = model
        self.api_keys = api_keys
        self.key_index = 0
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout
        )
        self.timeout = timeout
        self.cache: LRUCache[BaseModel] = LRUCache()

    @classmethod
    def from_settings(cls, settings: Settings):
        return GeminiWrapper(settings.base_url, settings.api_keys, settings.model, 30)

    async def _generate[T: BaseModel](
        self,
        config: CharacterConfig[T],
        prompt: str,
        timeout: float
    ) -> httpx.Response:
        # Generate 
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
                "maxOutputTokens": config.max_tokens,
                "thinkingConfig": {"thinkingLevel": "low"},
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
        cache_key = (self.model, config, prompt)
        if cached := self.cache.get(cache_key):
            logger.info("Gemini analysis cache hit")
            return cast(T, cached)

        if not self.api_keys:
            raise ValueError("At least one Gemini API key is required")

        time_taken = 0.0
        for attempt in range(len(self.api_keys)):
            key_index = self.key_index

            resp = await self._generate(config, prompt, self.timeout - time_taken)

            self.key_index = (key_index + 1) % len(self.api_keys)
            time_taken += resp.elapsed.total_seconds()

            if resp.status_code == 200:
                payload: dict = resp.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                model = config.schema.model_validate_json(text)
                self.cache.set(cache_key, model)
                return model
            if resp.status_code == 429:
                logger.warning(
                    "Gemini API rate limit reached for API key index %d",
                    key_index,
                )
            elif resp.status_code == 503:
                logger.warning("Gemini API unavailable; trying the next API key")
            else:
                resp.raise_for_status()

            delay = DELAY * (2 ** attempt)
            await asyncio.sleep(delay)
            if attempt == len(self.api_keys) - 1:
                resp.raise_for_status()

        raise AssertionError("Unreachable")

    async def close(self):
        return await self.client.aclose()
