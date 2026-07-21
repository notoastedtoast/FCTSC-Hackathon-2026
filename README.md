# ScamCheck

ScamCheck is a Vietnamese scam-message checker built with FastAPI, Pydantic,
PostgreSQL/Supabase, Psycopg, HTTPX, and a plain HTML/CSS/JavaScript frontend.

An online check uses one idempotent `POST /analyze` request. The server tries Gemini
primary, Gemini secondary, then Groq when configured; validates the structured result;
optionally generates a short Cô tâm lý response; and commits the result, audit record,
and replayable history data to PostgreSQL. Deterministic URL/text findings are advisory
evidence only and never override the provider's risk level.

When the browser is offline, a conservative rules engine runs locally. Offline results
are stored only in a bounded browser `localStorage` history and are never silently
uploaded. The service worker caches authored shell assets only, not API responses,
messages, results, cookies, or usage data.

## Setup

Requirements: Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

Copy `.env.example` to `.env`, then set:

- `GOOGLE_API_KEY` (or legacy `GEMINI_API_KEY`)
- `GOOGLE_MODEL` and `GOOGLE_FALLBACK_MODEL` if overriding defaults
- optional `GROQ_API_KEY` and `GROQ_MODEL`
- `DATABASE_URL` using the Supabase PostgreSQL transaction-pooler URL
- optional `AI_SESSION_CALL_LIMIT` (default: 10)

Passwords containing reserved URL characters must be URL-encoded in `DATABASE_URL`.
PostgreSQL stores `TIMESTAMPTZ` values as absolute instants; the history UI displays them
in Vietnam time (`Asia/Ho_Chi_Minh`, UTC+7).

## Run and verify

```sh
uv run uvicorn src.main:app --reload
uv run python -X utf8 -m unittest tests.test_api.ApiTests tests.test_analyzer.AnalyzerTests tests.test_gemini.MockGeminiIntegrationTests tests.test_database.AnalysisRepositoryTests tests.test_config.ConfigurationTests tests.test_catalog.CatalogTests tests.test_frontend.FrontendTests tests.test_regression.RegressionTests tests.test_deterministic_checker tests.test_url_extractor
uvx pyright
git diff --check
```

On systems with GNU Make, the equivalent shortcuts are `make run`,
`make test-offline`, `make test-online`, and `make typecheck`.
The online suite uses real credentials and may consume provider quota.

## Main API

- `GET /health` — process health without calling AI or PostgreSQL.
- `POST /analyze` — structured Detective result, optional Cô tâm lý response,
  deterministic supporting findings, and session usage. Send a stable
  `X-ScamCheck-Request-ID` when retrying.
- `GET /history/` — up to ten completed online results for the current cookie session.
- `DELETE /history/{analysis_id}` — hide one result from that session's history.
- `GET /session/ai-calls` — current session quota and audit metadata.
- `GET /analyses/{analysis_id}` — retrieve an analysis by its bearer-capability ID.
- `GET /scam-types` and `GET /scam-types/{id}` — authored scam library.
- `GET /openapi.json` — authoritative generated schema.

The session cookie groups quota, audit, and history records; it is not user
authentication. Submitted messages are untrusted model data and are stored in
PostgreSQL, so users should not submit passwords, OTPs, card numbers, or other secrets.

## Folder structure

```text
frontend/
  index.html              Application shell and hash-routed pages
  app.js                  API, server/offline history, rendering, practice, voice input
  offline-analyzer.js     Browser-only preliminary rules engine
  service-worker.js       Shell-assets-only offline cache
  styles.css              Responsive UI styles
src/
  main.py                 FastAPI composition, sessions, quota, routes, idempotency
  analyzer.py             Gemini/Groq fallback chain and structured validation
  database.py             PostgreSQL persistence and in-memory test backend
  schemas.py              Public Pydantic request/response contracts
  deterministic_checker.py Advisory text/domain signals
  url_extractor.py        Bounded URL extraction support
  frontend.py             Catalog and explicit frontend asset routes
  characters.py           Cô tâm lý voice contract
  config.py               Environment configuration
  data/scam_types.json    Authored scam catalog
tests/
  test_*.py               API, provider, database, frontend, and rule tests
  labeled_messages.json   24-message deterministic propagation corpus
  live_inputs.json        Credential-gated live provider corpus
  mock_gemini.py          Reusable in-process Gemini HTTP mock
```

Vercel uses the exported FastAPI application in `src/main.py`; no duplicate `app.py`
entrypoint is required.
