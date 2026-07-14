"""Public API request and response schemas."""

from pydantic import BaseModel, Field, field_validator


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


class ScamAnalysis(BaseModel):
    confidence: float = Field(ge=0, le=1, description="Likelihood the text is a scam, from 0 to 1")
    reasoning: str = Field(min_length=1, max_length=1_000)
    indicators: list[str] = Field(default_factory=list, max_length=20)
