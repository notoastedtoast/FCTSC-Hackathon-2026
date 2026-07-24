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
AI_SESSION_COOKIE_SECRET=replace-with-a-random-secret
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
.
├─ frontend/                    Browser UI and static assets
│  ├─ index.html                App shell
│  ├─ styles.css                UI styling
│  ├─ app-data.js               Shared frontend state and authored datasets
│  ├─ app-render.js             Result and message rendering helpers
│  ├─ app.js                    Main frontend controller and event wiring
│  ├─ offline-analyzer.js       Browser-only offline analysis fallback
│  ├─ service-worker.js         Offline shell cache
│  ├─ html2canvas.min.js        Client-side image export helper
│  ├─ scamcheck-logo.png        Brand asset
│  ├─ detective-avatar.png      Detective avatar
│  ├─ psychologist-avatar.png   Cô tâm lý avatar
│  └─ responder-avatar.png      Người ứng cứu avatar
│
├─ src/                         FastAPI backend
│  ├─ __init__.py
│  ├─ main.py                   API entrypoint
│  ├─ frontend.py               Frontend asset routes + scam library routes
│  ├─ schema.py                 Pydantic models, prompts, env settings
│  ├─ wrapper.py                Gemini HTTP wrapper
│  ├─ database.py               Async SQLite-backed history storage
│  ├─ deterministic_checker.py  Rules-based supporting checks
│  ├─ url_extractor.py          URL extraction helper
│  └─ data/
│     └─ scam_types.json        Authored scam library data
│
├─ tests/                       Automated tests and test fixtures
│  ├─ __init__.py
│  ├─ gemini_test_case.py
│  ├─ mock_gemini.py
│  ├─ test_api.py
│  ├─ test_config.py
│  ├─ test_deterministic_checker.py
│  ├─ test_frontend.py
│  ├─ test_gemini.py
│  ├─ test_live_api.py
│  ├─ test_url_extractor.py
│  ├─ labeled_messages.json
│  └─ live_inputs.json
│
├─ .env.example                 Example local environment config
├─ AGENTS.md                    Repo-specific agent instructions
├─ Makefile                     Common run/test shortcuts
├─ pyproject.toml               Python project metadata and dependencies
├─ pyrightconfig.json           Type-checker config
├─ README.md                    Project overview
└─ uv.lock                      Locked Python dependency versions
```

Notes:

- `__pycache__/` folders are intentionally omitted above.
- The backend and frontend are both served by `src/main.py`.
- The current checked-in backend is the smaller stable backend, even though some
  older branches/history used a larger architecture.

## Project file guide

- `frontend/index.html`
  - the main page shell with analyze, library, history, and practice views

- `frontend/app-data.js`
  - shared DOM references, constants, sample messages, quiz prompts, and
    Người ứng cứu action data

- `frontend/app-render.js`
  - safe DOM rendering for Detective, Cô tâm lý, and Người ứng cứu result sections

- `frontend/app.js`
  - the main browser logic: routing, API calls, history, voice input, offline mode,
    practice flow, and result sequencing

- `frontend/offline-analyzer.js`
  - conservative offline-only analyzer used when the browser has no network

- `frontend/service-worker.js`
  - caches only the app shell assets for offline loading

- `src/main.py`
  - FastAPI app, analyze/guide/history endpoints, session cookie use, and deployment fixes

- `src/frontend.py`
  - explicit file routes for frontend assets and the scam library API routes

- `src/schema.py`
  - request/response models, Gemini prompt config, and environment settings

- `src/wrapper.py`
  - low-level Gemini request/response wrapper with retry on 429

- `src/database.py`
  - async SQLite helper and session history persistence

- `src/deterministic_checker.py`
  - rule-based checks for suspicious text, short links, lookalike domains, and Cyrillic signals

- `src/url_extractor.py`
  - small URL extraction helper used by deterministic checks

- `tests/test_api.py`
  - API-level integration tests

- `tests/test_frontend.py`
  - checks for frontend asset presence and wiring

- `tests/test_deterministic_checker.py`
  - tests for the rule-based detector

- `tests/test_gemini.py` and `tests/mock_gemini.py`
  - Gemini-related test helpers

- `tests/test_live_api.py`
  - optional live tests that need real API credentials

## Deploy note

For Vercel, make sure the project environment includes at least:

- `GEMINI_API_KEY`
or
- `GOOGLE_API_KEY`

If `BASE_URL` is missing or invalid, `httpx` will fail when the backend creates the
Gemini client.
