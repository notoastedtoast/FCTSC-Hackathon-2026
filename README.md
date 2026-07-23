# ScamCheck

ScamCheck is a Vietnamese scam-message checker with a FastAPI backend and a plain
HTML/CSS/JavaScript frontend.

Right now, the checked-in code uses:

- Gemini for the main analysis
- a small rule-based checker for extra warning signals
- an optional calming guide generator
- session-based online history
- an offline browser fallback when the device has no network

For suspicious or dangerous results, the frontend can follow Cô tâm lý with a
one-choice exposure check and then show authored “Người ứng cứu” steps. This part
runs in the browser only; it does not call AI or save the exposure selection.

## Current stack

- Backend: Python 3.14, FastAPI, Pydantic, HTTPX
- Frontend: HTML, CSS, vanilla JavaScript
- Storage in the running app: in-memory SQLite adapter from `src/database.py`
- Package/dependency manager: `uv`
- Type checking: `pyright`

## Important current behavior

- The main app entrypoint is `src/main.py`.
- The backend currently exposes the smaller stable API, not the larger rewritten one.
- Online history is stored in memory in the running process because `src/main.py`
  creates `HistoryDatabase(":memory:")`.
- That means history resets when the server restarts, the process reloads, or Vercel
  redeploys.
- The per-session AI call counter is also stored in process memory, so it resets on restart.
- The current backend uses Gemini only. It does not currently use PostgreSQL,
  Supabase, Groq, or request-id idempotency in the live app path.

## Features in the current frontend

- Analyze suspicious messages
- Show low / medium / high risk
- Show supporting deterministic findings
- Generate an optional “Cô tâm lý” guide for medium/high risk saved results
- Browse a scam-type library
- View session history
- Save separate offline history in the browser
- Practice page with authored safe/scam examples
- Voice input button
- Service worker for offline shell caching

## Environment variables

Copy `.env.example` to `.env`.

Current `.env.example`:

```env
GEMINI_API_KEY=replace-with-your-gemini-api-key
BASE_URL=https://generativelanguage.googleapis.com/v1beta/
GEMINI_MODEL=gemini-3.5-flash
AI_SESSION_CALL_LIMIT=10
```

Also supported by the current code:

- `GOOGLE_API_KEY` as an alternative to `GEMINI_API_KEY`
- `GOOGLE_MODEL` as an alternative to `GEMINI_MODEL`

Notes:

- `BASE_URL` must be a valid Gemini API base URL.
- If the API key is missing, the app can start but analysis calls will fail.
- `AI_SESSION_CALL_LIMIT` controls how many AI-backed calls one browser session can make
  before the backend returns HTTP 429.

## Install

```sh
uv sync
```

## Run locally

```sh
make run
```

Equivalent command:

```sh
uv run uvicorn src.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/
```

## Tests and checks

Run the offline test suite:

```sh
make test-offline
```

Run live API tests:

```sh
make test-online
```

Run type checking:

```sh
make typecheck
```

Check patch formatting:

```sh
git diff --check
```

## Current API

### `POST /analyze/`

Analyzes one message and saves the result into the current session history.

Current request body shape is a raw JSON string, for example:

```json
"Tin nhắn cần kiểm tra"
```

Response:

- `success`
- `analysis` with:
  - `risk_level` as a number from `0.0` to `1.0`
  - `reasoning`
  - `suggestions`
  - `excerpts`
- `deterministic_findings`
- `deterministic_risk_floor`
- computed `risk_level` mapped to `low`, `medium`, or `high`

### `POST /guide/`

Generates or returns the cached calming guide for a saved history item.

Current request body shape is the saved history UUID as a JSON string.

### `GET /history/`

Returns the current browser session’s saved online history entries.

### `GET /history/{history_id}`

Returns one saved history entry by public UUID.

### `DELETE /history/{history_id}`

Deletes one history item only if it belongs to the active session.

### `GET /scam-types`

Returns the authored scam library. Supports optional filtering by group:

- `fake_bank`
- `fake_police`
- `prize`
- `fake_delivery`

### `GET /scam-types/{scam_type_id}`

Returns one scam-type detail record.

## Frontend routes served by FastAPI

The backend serves these explicit frontend assets:

- `/`
- `/styles.css`
- `/app.js`
- `/app-data.js`
- `/app-render.js`
- `/offline-analyzer.js`
- `/service-worker.js`
- `/scamcheck-logo.png`
- `/detective-avatar.png`
- `/psychologist-avatar.png`

## Folder structure

```text
frontend/
  index.html
  styles.css
  app.js
  app-data.js
  app-render.js
  offline-analyzer.js
  service-worker.js
  scamcheck-logo.png
  detective-avatar.png
  psychologist-avatar.png
  responder-avatar.png    Người ứng cứu action-bubble avatar
src/
  main.py
  frontend.py
  database.py
  wrapper.py
  schema.py
  deterministic_checker.py
  url_extractor.py
  data/
    scam_types.json

tests/
  test_api.py
  test_analyzer.py
  test_catalog.py
  test_config.py
  test_database.py
  test_deterministic_checker.py
  test_frontend.py
  test_gemini.py
  test_live_api.py
  test_regression.py
  test_url_extractor.py
  factories.py
  mock_gemini.py
  labeled_messages.json
  live_inputs.json
```

## Project file guide

- `src/main.py`: FastAPI app, session cookie handling, analyze/guide/history routes
- `src/frontend.py`: explicit frontend asset routes and scam library API
- `src/wrapper.py`: Gemini HTTP wrapper
- `src/schema.py`: Pydantic models, prompts, and environment settings
- `src/database.py`: async SQLite-backed history adapter used by the app
- `src/deterministic_checker.py`: extra rules-based warning checks
- `src/url_extractor.py`: URL extraction helpers for rule checks
- `frontend/app.js`: main browser controller logic
- `frontend/app-data.js`: shared state, constants, and authored frontend data
- `frontend/app-render.js`: rendering helpers

## Deploy note

For Vercel, make sure the project environment includes at least:

- `GEMINI_API_KEY`
or
- `GOOGLE_API_KEY`

If `BASE_URL` is missing or invalid, `httpx` will fail when the backend creates the
Gemini client.
