.PHONY: test evaluate reliability run

test:
	uv run python -m unittest discover -s tests 
evaluate:
	uv run python -m scripts.evaluate
reliability:
	uv run python -m scripts.reliability
run:
	uv run uvicorn src.main:app --reload
