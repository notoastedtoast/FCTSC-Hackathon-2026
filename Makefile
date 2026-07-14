test:
	uv run python -m unittest discover -s tests 
run:
	uv run uvicorn src.main:app --reload
