from src.schemas import SCAM_SCENARIOS, ScamScenario, ScamScenarioAssessment


def scenario_assessments(
    detected_scenario: ScamScenario | None = None,
) -> list[ScamScenarioAssessment]:
    return [
        ScamScenarioAssessment(
            scenario=scenario,
            detected=(detected := scenario == detected_scenario),
            confidence=0.9 if detected else 0.05,
            evidence="Có bằng chứng cụ thể." if detected else "Không có bằng chứng.",
        )
        for scenario in SCAM_SCENARIOS
    ]


def scenario_payload(
    detected_scenario: ScamScenario | None = None,
) -> list[dict[str, object]]:
    return [
        item.model_dump(mode="json")
        for item in scenario_assessments(detected_scenario)
    ]
