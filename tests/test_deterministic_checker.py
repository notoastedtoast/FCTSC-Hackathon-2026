from unittest import IsolatedAsyncioTestCase

import httpx

from src.deterministic_checker import (
    check_message,
    check_urls,
    find_impersonated_domain,
    resolve_shortened_url,
)

NON_SCAM_MESSAGES = {
    "vi_otp_delivery": {
        "text": (
            "Vietcombank: Mã OTP của quý khách là 482913, có hiệu lực 5 phút. "
            "Tuyệt đối không cung cấp mã này cho bất kỳ ai."
        ),
        "risk": "low",
    },
    "vi_completed_transfer": {
        "text": (
            "Tôi đã chuyển khoản tiền thuê nhà. Tuyệt đối không cung cấp mã OTP "
            "cho bất kỳ ai."
        ),
        "risk": "low",
    },
    "vi_official_government_link": {
        "text": "Hồ sơ đã được tiếp nhận tại https://dichvucong.gov.vn.",
        "risk": "low",
    },
    "en_otp_delivery": {
        "text": (
            "Your verification code is 731204. Do not share this code with anyone. "
            "Support will never ask for it."
        ),
        "risk": "low",
    },
    "fr_otp_delivery": {
        "text": (
            "Votre code de vérification est 619284. Ne communiquez ce code à "
            "personne."
        ),
        "risk": "low",
    },
    "es_completed_payment": {
        "text": "Tu pago mensual se procesó correctamente. No se requiere acción.",
        "risk": "low",
    },
    "ja_otp_delivery": {
        "text": "認証コードは 582104 です。このコードを他人に教えないでください。",
        "risk": "low",
    },
    "ru_otp_delivery": {
        "text": "Ваш код подтверждения: 428105. Никому не сообщайте этот код.",
        "risk": "medium",
    },
}


class DeterministicCheckerTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.client = httpx.AsyncClient(
            transport=httpx.MockTransport(self._handle_request),
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            302,
            headers={"location": "https://real.example/path"},
            request=request,
        )

    async def test_resolves_known_shorteners_without_fetching_destination(self) -> None:
        destination = await resolve_shortened_url("bit.ly/check", self.client)

        self.assertEqual(destination, "https://real.example/path")
        self.assertEqual([str(request.url) for request in self.requests], [
            "https://bit.ly/check",
        ])

    async def test_checks_extracted_urls_without_resolving_normal_urls(self) -> None:
        checks = await check_urls("Visit bit.ly/check and example.com", self.client)

        self.assertEqual(
            [(check.url, check.destination) for check in checks],
            [
                ("bit.ly/check", "https://real.example/path"),
                ("example.com", "https://example.com"),
            ],
        )
        self.assertEqual(len(self.requests), 1)

    async def test_keeps_original_url_when_shortener_resolution_fails(self) -> None:
        def fail_request(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("offline", request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(fail_request),
        ) as failing_client:
            checks = await check_urls("Visit bit.ly/check", failing_client)

        self.assertEqual(
            [(check.url, check.destination) for check in checks],
            [("bit.ly/check", "bit.ly/check")],
        )

    async def test_flags_bank_and_government_lookalikes(self) -> None:
        self.assertEqual(
            find_impersonated_domain("https://vietcornbank-login.example"),
            "vietcombank.com.vn",
        )
        self.assertEqual(
            find_impersonated_domain("https://vneid-check.example"),
            "vneid.gov.vn",
        )

    async def test_does_not_flag_official_bank_subdomains(self) -> None:
        self.assertIsNone(
            find_impersonated_domain("https://portal.vietcombank.com.vn/login")
        )

    async def test_combines_url_and_message_signals(self) -> None:
        result = await check_message(
            "Chuyển tiền ngay vào 012345678901 và gửi mã OTP trong vòng 10 phút: "
            "bit.ly/check",
            self.client,
        )

        self.assertEqual(result.risk_floor, "high")
        self.assertEqual(
            {finding.kind for finding in result.findings},
            {
                "shortened_url",
                "verification_code_request",
                "transfer_request",
                "account_number",
                "urgent_language",
            },
        )

    async def test_non_scam_messages_are_not_high_risk(self) -> None:
        for name, case in NON_SCAM_MESSAGES.items():
            with self.subTest(name=name):
                result = await check_message(case["text"], self.client)

                self.assertEqual(result.risk_floor, case["risk"])
                self.assertFalse(
                    any(finding.severity == "high" for finding in result.findings)
                )

    async def test_detects_cyrillic_bank_homograph(self) -> None:
        result = await check_message(
            "Mở https://vіetcombank.example/login",
            self.client,
        )

        self.assertEqual(result.risk_floor, "high")
        self.assertEqual(
            result.url_checks[0].impersonated_domain,
            "vietcombank.com.vn",
        )
        self.assertTrue(result.url_checks[0].has_cyrillic)
