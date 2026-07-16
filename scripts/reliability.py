"""Run ten live calls and report Gemini structured-output reliability."""

import asyncio

from src.analyzer import AnalysisError, ScamAnalyzer
from src.config import load_settings
from src.schemas import AnalyzeRequest
from scripts.evaluate import load_cases


async def check_reliability() -> int:
    analyzer = ScamAnalyzer(load_settings())
    cases = load_cases()[:10]
    results: list[tuple[str, bool, str]] = []
    try:
        for case in cases:
            try:
                result = await analyzer.analyze(AnalyzeRequest(text=case.text))
                structured = not result.fallback_used
                detail = "VALID" if structured else "DEFAULTED"
            except AnalysisError:
                structured = False
                detail = "REQUEST_ERROR"
            results.append((case.id, structured, detail))
    finally:
        await analyzer.aclose()

    print(f"{'CALL':<16} {'STRUCTURED':<12} RESULT")
    print("-" * 40)
    for case_id, structured, detail in results:
        print(f"{case_id:<16} {str(structured):<12} {detail}")
    successes = sum(structured for _, structured, _ in results)
    print("-" * 40)
    print(f"Structured: {successes}/10 | Required: 9/10")
    return 0 if successes >= 9 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check_reliability()))
