from unittest import IsolatedAsyncioTestCase
from uuid import UUID
from unittest.mock import AsyncMock, patch

import httpx

from src import main
from src.database import HistoryDatabase
from src.schema import Analysis, DetectiveAnalysis, GuideOutput, ResponderOutput

from .mock_gemini import MockGeminiAPI


class AnalyzeAPITests(IsolatedAsyncioTestCase):
    history_id = "9b69b1ea-9765-46bd-b3a9-03e87618c36d"

    async def asyncSetUp(self) -> None:
        self.mock_gemini = MockGeminiAPI()
        self.gemini = await self.mock_gemini.create_wrapper()
        self.database = AsyncMock(spec=HistoryDatabase)
        self.database.save_analysis.return_value = self.history_id

        self._original_overrides = main.app.dependency_overrides.copy()

        async def get_mock_client():
            return self.gemini

        async def get_mock_database():
            return self.database

        main.app.dependency_overrides[main.get_client] = get_mock_client
        main.app.dependency_overrides[main.get_database] = get_mock_database
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.gemini.close()
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self._original_overrides)

    async def test_analyze_returns_and_saves_gemini_result(self) -> None:
        analysis = DetectiveAnalysis(
            risk_level=0.9,
            reasoning="The request is suspicious.",
            suggestions=["Do not respond."],
            excerpts={"Urgent": "Creates artificial urgency."},
        )
        self.mock_gemini.add_analysis(analysis)
        result = Analysis(
            success=True,
            id=UUID(self.history_id),
            analysis=analysis,
        )

        response = await self.client.post("/analyze/", json="Send money now")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            result.model_dump(mode="json"),
        )
        self.assertIsNotNone(response.cookies.get("session_id"))
        self.database.save_analysis.assert_awaited_once()

        session_id, message, saved_analysis = self.database.save_analysis.await_args.args
        self.assertEqual(session_id, response.cookies["session_id"])
        self.assertEqual(message, "Send money now")
        self.assertEqual(saved_analysis, result)
        self.assertEqual(len(self.mock_gemini.requests), 1)

    async def test_analyze_returns_unsuccessful_response_when_gemini_fails(self) -> None:
        with patch.object(
            self.gemini,
            "generate",
            AsyncMock(side_effect=RuntimeError("Gemini unavailable")),
        ):
            response = await self.client.post("/analyze/", json="Send money now")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"success": False, "id": None, "analysis": None, "deterministic_findings": [],
             "deterministic_risk_floor": "low", "risk_level": None},
        )
        self.database.save_analysis.assert_not_awaited()

    async def test_guide_generates_and_saves_output_for_history_uuid(self) -> None:
        analysis = DetectiveAnalysis(
            risk_level=0.5,
            reasoning="Safe.",
            suggestions=[],
            excerpts={},
        )
        guide = GuideOutput(data="Stay calm and verify the sender.")
        self.mock_gemini.add_analysis(guide)
        self.database.get_history_item.return_value = {
            "id": self.history_id,
            "message": "Hello",
            "analysis": Analysis(success=True, analysis=analysis).model_dump(),
            "guide_output": None,
            "created_at": "2026-07-19 12:00:00",
        }

        with patch.object(main.settings, "ai_session_call_limit", 1):
            response = await self.client.post(
                "/guide/",
                json=self.history_id,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), guide.model_dump())
        self.assertEqual(len(self.mock_gemini.requests), 1)
        self.database.save_guide_output.assert_awaited_once_with(
            self.history_id, guide.data
        )

    async def test_guide_returns_saved_output_without_ai_call(self) -> None:
        analysis = DetectiveAnalysis(
            risk_level=0.5,
            reasoning="Potentially suspicious.",
            suggestions=[],
            excerpts={},
        )
        self.database.get_history_item.return_value = {
            "id": self.history_id,
            "message": "Hello",
            "analysis": Analysis(success=True, analysis=analysis).model_dump(),
            "guide_output": "Already generated.",
            "created_at": "2026-07-19 12:00:00",
        }

        response = await self.client.post("/guide/", json=self.history_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": "Already generated."})
        self.assertEqual(len(self.mock_gemini.requests), 0)
        self.database.save_guide_output.assert_not_awaited()

    async def test_guide_returns_no_output_for_low_risk_analysis(self) -> None:
        analysis = DetectiveAnalysis(
            risk_level=0.1,
            reasoning="Safe.",
            suggestions=[],
            excerpts={},
        )
        self.database.get_history_item.return_value = {
            "id": self.history_id,
            "message": "Hello",
            "analysis": Analysis(success=True, analysis=analysis).model_dump(),
            "guide_output": "Old output.",
            "created_at": "2026-07-19 12:00:00",
        }

        response = await self.client.post("/guide/", json=self.history_id)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(len(self.mock_gemini.requests), 0)
        self.database.save_guide_output.assert_not_awaited()

    async def test_guide_rejects_unknown_history_uuid(self) -> None:
        self.database.get_history_item.return_value = None

        response = await self.client.post("/guide/", json=self.history_id)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "History item not found"})

    async def test_responder_generates_after_a_selected_scenario(self) -> None:
        analysis = DetectiveAnalysis(risk_level=0.9, reasoning="Risk.", suggestions=[], excerpts={})
        output = ResponderOutput(steps=["Gọi 1900545413 ngay.", "Khóa tài khoản."])
        self.mock_gemini.add_analysis(output)
        self.database.get_history_item.return_value = {"analysis": Analysis(success=True, analysis=analysis).model_dump()}

        response = await self.client.post("/responder/", json={"history_id": self.history_id, "choice": "sent-money", "hotlines": {"Vietcombank": "1900545413", "Fake": "999"}, "bank": "Vietcombank"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), output.model_dump())
        self.assertIn("1900545413", self.mock_gemini.request_json()["contents"][0]["parts"][0]["text"])
        self.assertIn('"police_hotline": "113"', self.mock_gemini.request_json()["contents"][0]["parts"][0]["text"])
        self.assertIn('"selected_bank": "Vietcombank"', self.mock_gemini.request_json()["contents"][0]["parts"][0]["text"])
        self.assertNotIn("19009247", self.mock_gemini.request_json()["contents"][0]["parts"][0]["text"])
        self.assertNotIn("999", self.mock_gemini.request_json()["contents"][0]["parts"][0]["text"])
        self.database.save_responder_output.assert_awaited_once_with(
            self.history_id, output.model_dump_json()
        )

    async def test_telephones_are_public(self) -> None:
        response = await self.client.get("/telephones")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["Vietcombank"], "1900545413")

    async def test_responder_rejects_unknown_output_phone(self) -> None:
        analysis = DetectiveAnalysis(risk_level=0.9, reasoning="Risk.", suggestions=[], excerpts={})
        self.mock_gemini.add_analysis(ResponderOutput(steps=["Gọi 999.", "Khóa tài khoản."]))
        self.database.get_history_item.return_value = {"analysis": Analysis(success=True, analysis=analysis).model_dump()}

        response = await self.client.post("/responder/", json={"history_id": self.history_id, "choice": "sent-money", "hotlines": {}})

        self.assertEqual(response.status_code, 502)

    async def test_analyze_enforces_per_session_call_limit(self) -> None:
        analysis = DetectiveAnalysis(
            risk_level=0.1,
            reasoning="Safe.",
            suggestions=[],
            excerpts={},
        )
        self.mock_gemini.add_analysis(analysis)

        with patch.object(main.settings, "ai_session_call_limit", 1):
            first = await self.client.post(
                "/analyze/",
                json="Hello",
                headers={"cookie": "session_id=session-a"},
            )
            second = await self.client.post(
                "/analyze/",
                json="Hello again",
                headers={
                    "cookie": f"session_id=session-a; ai_call_count={first.cookies['ai_call_count']}"
                },
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json(), {"detail": "AI session call limit reached"})
        self.assertEqual(len(self.mock_gemini.requests), 1)

    async def test_delete_history_item_for_session(self) -> None:
        self.database.delete_history.return_value = True

        response = await self.client.delete(
            f"/history/{self.history_id}",
            headers={"cookie": "session_id=session-a"},
        )

        self.assertEqual(response.status_code, 204)
        self.database.delete_history.assert_awaited_once_with(
            "session-a", self.history_id
        )

    async def test_delete_missing_history_item_returns_not_found(self) -> None:
        self.database.delete_history.return_value = False
        response = await self.client.delete(
            f"/history/{self.history_id}",
            headers={"cookie": "session_id=session-a"},
        )
        self.assertEqual(response.status_code, 404)

    async def test_get_history_item_is_public(self) -> None:
        item = {
            "id": self.history_id,
            "message": "Hello",
            "analysis": {"success": True, "analysis": None},
            "guide_output": "Stay calm.",
            "created_at": "2026-07-19 12:00:00",
        }
        self.database.get_history_item.return_value = item

        response = await self.client.get(f"/history/{self.history_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), item)
        self.database.get_history_item.assert_awaited_once_with(self.history_id)

    async def test_scam_catalog_is_served_from_authored_data(self) -> None:
        response = await self.client.get("/scam-types")

        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual(len(items), 12)
        self.assertEqual(
            {item["group"] for item in items},
            {"fake_bank", "fake_police", "prize", "fake_delivery"},
        )

    async def test_scam_catalog_supports_filter_and_detail(self) -> None:
        filtered = await self.client.get("/scam-types", params={"group": "fake_bank"})
        detail = await self.client.get("/scam-types/bank-otp-support")

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.json()), 3)
        self.assertTrue(all(item["group"] == "fake_bank" for item in filtered.json()))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], "bank-otp-support")

    async def test_unknown_scam_type_returns_not_found(self) -> None:
        response = await self.client.get("/scam-types/not-in-catalog")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Scam type not found"})
