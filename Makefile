.PHONY: test test-offline test-online run

test: test-offline

test-offline:
	.venv/bin/python -m unittest -f tests.test_api tests.test_gemini

test-online:
	.venv/bin/python -m unittest -v tests.test_live_api

run:
	.venv/bin/uvicorn src.main:app --reload
