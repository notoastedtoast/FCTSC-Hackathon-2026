.PHONY: test-offline test-online run

test-offline:
	.venv/bin/python -m unittest tests.test_api.ApiTests

test-online:
	.venv/bin/python -m unittest tests.test_api.LiveGeminiApiTests

run:
	.venv/bin/uvicorn src.main:app --reload
