"""Reusable unittest setup for tests that call Gemini."""

from unittest import IsolatedAsyncioTestCase

from src.wrapper import GeminiWrapper

from .mock_gemini import MockGeminiAPI


class GeminiTestCase(IsolatedAsyncioTestCase):
    """Provide a real wrapper connected to an in-process Gemini mock."""

    async def asyncSetUp(self) -> None:
        self.mock_gemini = MockGeminiAPI()
        self.gemini: GeminiWrapper = await self.mock_gemini.create_wrapper()

    async def asyncTearDown(self) -> None:
        await self.gemini.close()
