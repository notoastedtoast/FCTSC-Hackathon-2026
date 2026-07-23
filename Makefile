.PHONY: test test-offline test-online typecheck run

test: test-offline

test-offline:
	uv run python -X utf8 -m unittest -f tests.test_api.ApiTests tests.test_analyzer.AnalyzerTests tests.test_gemini.MockGeminiIntegrationTests tests.test_database.AnalysisRepositoryTests tests.test_config.ConfigurationTests tests.test_catalog.CatalogTests tests.test_frontend.FrontendTests tests.test_regression.RegressionTests tests.test_deterministic_checker tests.test_url_extractor

test-online:
	uv run python -X utf8 -m unittest -v tests.test_live_api

typecheck:
	uvx pyright

run:
	uv run uvicorn src.main:app --reload
