"""In-process mock for Gemini's ``generateContent`` API."""

from collections import deque
from collections.abc import Mapping
from copy import deepcopy
from datetime import timedelta
import json
from typing import Any

import httpx
from pydantic import BaseModel

from src.wrapper import GeminiWrapper

GEMINI_RESPONSE_STRUCTURE: dict[str, Any] = {
    "candidates": [
        {
            "content": {
                "parts": [],
            },
        },
    ],
}


class MockGeminiAPI:
    """Queue Gemini responses and expose them through an HTTPX transport."""

    base_url = "https://mock-gemini.test/"

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._responses: deque[httpx.Response] = deque()
        self.transport = httpx.MockTransport(self._handle_request)

    def add_response(
        self,
        payload: Mapping[str, Any] | None = None,
        *,
        status_code: int = 200,
    ) -> None:
        """Queue a raw Gemini API response."""

        self._responses.append(httpx.Response(status_code, json=payload or {}))

    def add_analysis(self, analysis: BaseModel) -> None:
        """Queue a successful structured response for ``GeminiWrapper``."""

        payload = deepcopy(GEMINI_RESPONSE_STRUCTURE)
        payload["candidates"][0]["content"]["parts"].append(
            {"text": analysis.model_dump_json()}
        )
        self.add_response(payload)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            transport=self.transport,
        )

    async def create_wrapper(
        self,
        *,
        model: str = "gemini-test",
        api_keys: list[str] | None = None,
        timeout: int = 1,
    ) -> GeminiWrapper:
        """Build a ``GeminiWrapper`` that sends requests to this mock."""

        wrapper = GeminiWrapper(
            self.base_url,
            api_keys or ["test-api-key"],
            model,
            timeout,
        )
        await wrapper.client.aclose()
        wrapper.client = self.client()
        return wrapper

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)

        if request.method != "POST" or not request.url.path.endswith(
            ":generateContent"
        ):
            return httpx.Response(404, json={"error": "Unknown Gemini endpoint"})
        if not self._responses:
            return httpx.Response(500, json={"error": "No mock response queued"})

        response = self._responses.popleft()
        response = httpx.Response(
            response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )
        response.elapsed = timedelta()
        return response

    def request_json(self, index: int = -1) -> dict[str, Any]:
        """Return a captured request payload for assertions."""

        return json.loads(self.requests[index].content)
