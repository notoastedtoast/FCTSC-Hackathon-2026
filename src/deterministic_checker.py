import asyncio
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx

from .url_extractor import extract_urls

SHORTENER_HOSTS = frozenset({
    "bit.ly", "buff.ly", "cutt.ly", "is.gd", "ow.ly", "rb.gy", "rebrand.ly",
    "shorturl.at", "t.co", "tiny.cc", "tinyurl.com",
})
MAX_REDIRECTS = 5
MAX_URLS = 5
PROTECTED_DOMAINS = frozenset({
    "acb.com.vn", "agribank.com.vn", "baohiemxahoi.gov.vn", "bidv.com.vn",
    "chinhphu.vn", "dichvucong.gov.vn", "gdt.gov.vn", "hdbank.com.vn",
    "mbbank.com.vn", "moj.gov.vn", "mps.gov.vn", "sacombank.com.vn",
    "shb.com.vn", "techcombank.com", "tpbank.com.vn", "vib.com.vn",
    "vietnam.gov.vn", "vietcombank.com.vn", "vietinbank.vn", "vneid.gov.vn",
    "vpbank.com.vn",
})
LOOKALIKE_RATIO = 0.86
CYRILLIC = re.compile(r"[\u0400-\u052f\u2de0-\u2dff\ua640-\ua69f]")
CYRILLIC_TOKEN = re.compile(r"\S*[\u0400-\u052f\u2de0-\u2dff\ua640-\ua69f]\S*")
CYRILLIC_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "і": "i", "ј": "j", "к": "k", "м": "m",
    "н": "h", "о": "o", "р": "p", "с": "c", "т": "t", "у": "y",
    "х": "x",
})

VERIFICATION_CODE_REQUEST = re.compile(
    r"\b(?:gửi|cung cấp|đọc|nhập).{0,30}"
    r"(?:mã\s*(?:otp|xác thực|xác minh|bảo mật)|otp)\b",
    re.IGNORECASE,
)
TRANSFER_REQUEST = re.compile(
    r"\b(?:(?:hãy|vui\s*lòng|yêu\s*cầu|cần|phải)\s+"
    r"(?:chuyển\s*(?:tiền|khoản)|thanh\s*toán|nạp\s*tiền)|"
    r"(?:chuyển\s*(?:tiền|khoản)|thanh\s*toán|nạp\s*tiền)"
    r".{0,20}(?:ngay|gấp|vào\s+(?:tài\s*khoản|stk|\d)))\b",
    re.IGNORECASE,
)
ACCOUNT_NUMBER = re.compile(r"\b\d{9,19}\b")
NEGATED_REQUEST = re.compile(
    r"\b(?:không|đừng|tuyệt\s*đối\s*không).{0,15}"
    r"(?:gửi|cung\s*cấp|đọc|nhập)\b",
    re.IGNORECASE,
)
URGENT_LANGUAGE = re.compile(
    r"\b(?:khẩn\s*cấp|ngay\s*lập\s*tức|trong\s*(?:vòng\s*)?\d+\s*phút|"
    r"tài\s*khoản.{0,20}(?:khóa|bị\s*khóa))\b",
    re.IGNORECASE,
)
TEXT_RULES = (
    ("transfer_request", TRANSFER_REQUEST),
    ("account_number", ACCOUNT_NUMBER),
    ("urgent_language", URGENT_LANGUAGE),
    ("cyrillic_text", CYRILLIC_TOKEN),
)
HIGH_RISK_COMBINATIONS = (
    frozenset({"verification_code_request", "transfer_request"}),
    frozenset({"transfer_request", "account_number", "urgent_language"}),
)


@dataclass(frozen=True)
class URLCheck:
    url: str
    destination: str
    impersonated_domain: str | None = None
    has_cyrillic: bool = False


@dataclass(frozen=True)
class RuleFinding:
    kind: str
    severity: Literal["medium", "high"]
    excerpt: str
    details: str | None = None


@dataclass(frozen=True)
class DeterministicResult:
    url_checks: list[URLCheck]
    findings: list[RuleFinding]
    risk_floor: Literal["low", "medium", "high"]


def _normalise_url(url: str) -> str:
    return url if urlsplit(url).scheme else f"https://{url}"


def _is_shortener(url: str) -> bool:
    return urlsplit(_normalise_url(url)).hostname in SHORTENER_HOSTS


def _hostname(url: str) -> str | None:
    host = urlsplit(_normalise_url(url)).hostname
    if host is None:
        return None
    try:
        return host.encode("ascii").decode("idna").lower()
    except UnicodeError:
        return host.lower()


def _has_cyrillic_hostname(url: str) -> bool:
    host = _hostname(url)
    return host is not None and CYRILLIC.search(host) is not None


def find_impersonated_domain(url: str) -> str | None:
    """Return the protected domain a non-official hostname appears to imitate."""
    host = _hostname(url)
    if host is None:
        return None
    for domain in PROTECTED_DOMAINS:
        if host == domain or host.endswith(f".{domain}"):
            continue
        brand = domain.split(".", 1)[0]
        for label in host.split("."):
            for candidate in (label, *label.split("-")):
                compact_candidate = candidate.replace("-", "").translate(
                    CYRILLIC_CONFUSABLES
                )
                if brand in compact_candidate:
                    return domain
                if (
                    len(brand) >= 5
                    and SequenceMatcher(None, compact_candidate, brand).ratio()
                    >= LOOKALIKE_RATIO
                ):
                    return domain
    return None


async def resolve_shortened_url(url: str, client: httpx.AsyncClient) -> str:
    """Follow known shortening-service redirects without fetching the final site."""
    current = _normalise_url(url)
    if not _is_shortener(current):
        return current

    for _ in range(MAX_REDIRECTS):
        response = await client.get(current, follow_redirects=False)
        location = response.headers.get("location")
        if not location or not response.is_redirect:
            return current
        destination = urljoin(current, location)
        if not _is_shortener(destination):
            return destination
        current = destination
    return current


async def check_urls(text: str, client: httpx.AsyncClient | None = None) -> list[URLCheck]:
    """Extract URLs and deterministically resolve recognized shortened links."""
    urls = extract_urls(text)[:MAX_URLS]
    if client is None:
        return [
            URLCheck(
                url,
                destination := _normalise_url(url),
                find_impersonated_domain(url) or find_impersonated_domain(destination),
                _has_cyrillic_hostname(url) or _has_cyrillic_hostname(destination),
            )
            for url in urls
        ]
    else:
        async def inspect(url: str) -> URLCheck:
            try:
                destination = await resolve_shortened_url(url, client)
            except httpx.HTTPError:
                destination = url
            return URLCheck(
                url,
                destination,
                find_impersonated_domain(url) or find_impersonated_domain(destination),
                _has_cyrillic_hostname(url) or _has_cyrillic_hostname(destination),
            )

        return list(await asyncio.gather(*(inspect(url) for url in urls)))


def _url_findings(url_checks: list[URLCheck]) -> list[RuleFinding]:
    return [
        *(
            RuleFinding(
                "url_lookalike",
                "high",
                check.url,
                f"Imitates {check.impersonated_domain}",
            )
            for check in url_checks
            if check.impersonated_domain is not None
        ),
        *(
            RuleFinding("shortened_url", "medium", check.url, check.destination)
            for check in url_checks
            if _is_shortener(check.url)
        ),
        *(
            RuleFinding("cyrillic_hostname", "medium", check.url)
            for check in url_checks
            if check.has_cyrillic
        ),
    ]


def _verification_code_findings(text: str) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for match in VERIFICATION_CODE_REQUEST.finditer(text):
        context = text[max(0, match.start() - 25):match.end()]
        if NEGATED_REQUEST.search(context) is None:
            findings.append(
                RuleFinding("verification_code_request", "medium", match.group())
            )
    return findings


def _text_findings(text: str) -> list[RuleFinding]:
    findings = _verification_code_findings(text)
    for kind, pattern in TEXT_RULES:
        findings.extend(
            RuleFinding(kind, "medium", match.group())
            for match in pattern.finditer(text)
        )
    return findings


def _risk_floor(
    findings: list[RuleFinding],
) -> Literal["low", "medium", "high"]:
    kinds = {finding.kind for finding in findings}
    is_high_risk = (
        any(finding.severity == "high" for finding in findings)
        or any(combination <= kinds for combination in HIGH_RISK_COMBINATIONS)
    )
    if is_high_risk:
        return "high"
    return "medium" if findings else "low"


async def check_message(
    text: str,
    client: httpx.AsyncClient | None = None,
) -> DeterministicResult:
    """Collect deterministic scam signals without invoking an AI model."""
    url_checks = await check_urls(text, client)
    findings = [*_url_findings(url_checks), *_text_findings(text)]
    return DeterministicResult(url_checks, findings, _risk_floor(findings))
