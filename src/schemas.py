"""Public API request and response schemas."""

from datetime import datetime
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ScamScenario = Literal[
    "malicious_fake_links",
    "close_contact_impersonation_conflict",
    "authority_or_business_impersonation",
    "credential_or_otp_theft",
    "payment_or_invoice_fraud",
    "investment_or_crypto_fraud",
    "romance_or_relationship_fraud",
    "prize_refund_or_advance_fee",
    "job_or_task_fraud",
    "tech_support_or_remote_access",
    "extortion_or_threats",
    "marketplace_or_delivery_fraud",
]
RiskLevel = Literal["safe", "suspicious", "dangerous"]
ActionText = Annotated[str, Field(min_length=1, max_length=300)]
AnalysisId = Annotated[
    str,
    Field(
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
        description="128-bit cryptographically random analysis ID",
    ),
]

SCAM_SCENARIO_GUIDANCE: tuple[tuple[ScamScenario, str], ...] = (
    (
        "malicious_fake_links",
        "Fake, shortened, lookalike, or malware links and QR codes intended to steal data.",
    ),
    (
        "close_contact_impersonation_conflict",
        "A fake friend, partner, or family member using an emergency, interpersonal conflict, "
        "secrecy, money request, or details that conflict with the known relationship.",
    ),
    (
        "authority_or_business_impersonation",
        "Impersonation of a bank, employer, police, government agency, or trusted company.",
    ),
    (
        "credential_or_otp_theft",
        "Requests for passwords, recovery codes, one-time passcodes, identity data, "
        "or account access.",
    ),
    (
        "payment_or_invoice_fraud",
        "Changed payment details, fake invoices, wire transfers, gift cards, "
        "or urgent payment demands.",
    ),
    (
        "investment_or_crypto_fraud",
        "Guaranteed returns, fake trading platforms, cryptocurrency transfers, "
        "or investment pressure.",
    ),
    (
        "romance_or_relationship_fraud",
        "Emotional grooming or a fabricated relationship used to obtain money, access, "
        "or sensitive data.",
    ),
    (
        "prize_refund_or_advance_fee",
        "Fake prizes, refunds, grants, inheritances, or loans that require a fee "
        "or information first.",
    ),
    (
        "job_or_task_fraud",
        "Fake employment, paid task, mystery shopper, equipment purchase, or recruitment offers.",
    ),
    (
        "tech_support_or_remote_access",
        "Fake support alerts seeking software installation, screen sharing, remote access, "
        "or payment.",
    ),
    (
        "extortion_or_threats",
        "Blackmail, fabricated legal threats, account suspension, intimidation, "
        "or demands under pressure.",
    ),
    (
        "marketplace_or_delivery_fraud",
        "Fake buyers, sellers, escrow, shipping notices, delivery fees, "
        "or off-platform transactions.",
    ),
)

SCAM_SCENARIOS: tuple[ScamScenario, ...] = tuple(
    scenario for scenario, _ in SCAM_SCENARIO_GUIDANCE
)


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000, description="Message to assess")
    source: str | None = Field(
        default=None,
        max_length=100,
        description="Optional source, such as email, sms, or chat",
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class ScamScenarioAssessment(BaseModel):
    scenario: ScamScenario
    detected: bool
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=500)


class IndicatorEvidence(BaseModel):
    """A concrete warning sign and an exact quote from the submitted message."""

    label: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=500)


DEFAULT_ACTIONS: tuple[str, str, str] = (
    "Không trả lời, chuyển tiền hoặc cung cấp thông tin nhạy cảm.",
    "Tự liên hệ tổ chức hoặc người gửi qua kênh chính thức.",
    "Lưu lại tin nhắn và nhờ người tin cậy kiểm tra nếu còn phân vân.",
)


class ScamAnalysis(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    confidence: float = Field(
        ge=0, le=1, description="Likelihood the text is a scam, from 0 to 1"
    )
    reasoning: str = Field(min_length=1, max_length=1_000)
    indicators: list[str] = Field(default_factory=list, max_length=4)
    indicator_evidence: list[IndicatorEvidence] = Field(default_factory=list, max_length=4)
    actions: list[ActionText] = Field(
        default_factory=lambda: list(DEFAULT_ACTIONS), min_length=3, max_length=3
    )
    scenarios: list[ScamScenarioAssessment] = Field(min_length=12, max_length=12)
    main_categories: list[ScamScenario] = Field(default_factory=list, max_length=4)
    provider_risk_level: RiskLevel | None = Field(
        default=None, alias="risk_level", exclude=True
    )
    fallback_used: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def must_assess_every_scenario_in_order(self) -> "ScamAnalysis":
        actual_scenarios = tuple(assessment.scenario for assessment in self.scenarios)
        if actual_scenarios != SCAM_SCENARIOS:
            raise ValueError(
                "scenarios must assess all 12 scam scenarios in the required order"
            )
        detected_categories = cast(
            list[ScamScenario],
            [assessment.scenario for assessment in self.scenarios if assessment.detected],
        )[:4]
        if self.main_categories:
            if any(category not in detected_categories for category in self.main_categories):
                raise ValueError("main_categories must contain detected scenarios only")
        else:
            self.main_categories = detected_categories
        return self


class DetectiveResult(ScamAnalysis):
    title: Literal["Thám tử"] = "Thám tử"
    risk_level: RiskLevel


class CharacterReply(BaseModel):
    character_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=50)
    message: str = Field(min_length=1, max_length=400)


class AiCallUsage(BaseModel):
    used: int = Field(ge=0)
    limit: int = Field(gt=0)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


class AnalyzeResponse(BaseModel):
    id: AnalysisId
    detective: DetectiveResult
    character: CharacterReply | None = None
    character_notice: str | None = None
    usage: AiCallUsage


class AiCallLog(BaseModel):
    id: AnalysisId
    created_at: datetime
    kind: Literal["detective", "character"]
    input_length: int = Field(ge=0, le=10_000)
    success: bool | None
    summary: str = Field(min_length=1, max_length=500)


class AiCallHistory(BaseModel):
    usage: AiCallUsage
    calls: list[AiCallLog]


class StoredAnalysis(ScamAnalysis):
    id: AnalysisId
    text: str
    source: str | None = None
    created_at: datetime
