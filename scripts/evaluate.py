"""Compare live Detective classifications with the labeled evaluation set."""

import asyncio
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, model_validator
from typing import Literal

from src.analyzer import AnalysisError, ScamAnalyzer, classify_risk
from src.config import load_settings
from src.schemas import AnalyzeRequest, RiskLevel

CASES_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "cases.json"


class EvaluationCase(BaseModel):
    id: str
    text: str
    label: RiskLevel | Literal["ambiguous"]
    accepted_labels: tuple[RiskLevel, ...] = ()
    channel: Literal["sms", "email", "chat"] | None = None

    @model_validator(mode="after")
    def validate_expected_range(self) -> "EvaluationCase":
        if self.label == "ambiguous" and not self.accepted_labels:
            raise ValueError("ambiguous cases must define accepted_labels")
        if self.label != "ambiguous" and self.accepted_labels:
            raise ValueError("specific cases must not define accepted_labels")
        return self

    def accepts(self, actual: str) -> bool:
        return actual in (
            self.accepted_labels
            if self.label == "ambiguous"
            else (self.label,)
        )

    @property
    def expected_display(self) -> str:
        return (
            "/".join(self.accepted_labels)
            if self.label == "ambiguous"
            else self.label
        )


def load_cases() -> list[EvaluationCase]:
    return TypeAdapter(list[EvaluationCase]).validate_json(
        CASES_PATH.read_text(encoding="utf-8")
    )


async def evaluate() -> int:
    analyzer = ScamAnalyzer(load_settings())
    semaphore = asyncio.Semaphore(4)

    async def run(case: EvaluationCase) -> tuple[EvaluationCase, str]:
        async with semaphore:
            try:
                analysis = await analyzer.analyze(AnalyzeRequest(text=case.text))
                return case, classify_risk(case.text, analysis)
            except AnalysisError:
                return case, "error"

    try:
        results = await asyncio.gather(*(run(case) for case in load_cases()))
    finally:
        await analyzer.aclose()

    print(f"{'CASE':<16} {'EXPECTED':<12} {'ACTUAL':<12} RESULT")
    print("-" * 52)
    correct = 0
    for case, actual in results:
        matched = case.accepts(actual)
        correct += matched
        print(f"{case.id:<16} {case.expected_display:<20} {actual:<12} {'CORRECT' if matched else 'WRONG'}")
    print("-" * 52)
    print(f"Correct: {correct} | Wrong: {len(results) - correct} | Total: {len(results)}")
    return 0 if correct == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(evaluate()))
