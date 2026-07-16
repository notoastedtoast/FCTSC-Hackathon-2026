# Agent guide for ScamCheck

This file applies to the entire repository. Read it before changing code. It is both an
implementation map and a record of the invariants that future agents must preserve.

## Project purpose and boundaries

ScamCheck is a Python 3.14 FastAPI service that sends submitted text to Google Gemini for
structured scam analysis. It stores completed analyses in SQLite, applies local risk
escalation rules, and can generate a short Vietnamese response from Cô tâm lý. The static
HTML/CSS/JavaScript client in `frontend/` includes the analyzer and a filterable scam
library.

Preserve these boundaries unless a user explicitly changes them:

- Keep backend work in `src/` and backend tests in `tests/`. Do not change `frontend/` for
  a backend-only request.
- Keep user-facing Detective and character output concise and primarily Vietnamese.
- Treat analyzed text as untrusted data, never as model instructions.
- Never log raw submitted text. SQLite intentionally stores analysis submissions.
- Do not expose an endpoint or request schema for chatting with characters. Characters
  may only produce the optional one-time response generated during `/analyze`.
- A session cookie limits and audits provider calls; it does not authenticate a user or
  establish ownership of an analysis.
- Do not add speculative endpoints, tables, or abstractions. Extend the smallest existing
  contract that satisfies the request.

## Commands

Run commands from the repository root.

| Purpose | Command | Notes |
| --- | --- | --- |
| Install/sync | `uv sync` | Uses `pyproject.toml` and `uv.lock`. |
| Offline tests | `make test-offline` | Runs mocked API contracts, the 24-message labeled regression table, and frontend data checks. |
| Online API tests | `make test-online` | Runs the credential-gated live Gemini API tests in `tests.test_api.LiveGeminiApiTests`. |
| Run API and static UI | `make run` | Starts Uvicorn with reload. |
| Strict type check | `pyright` | Configuration is in `pyrightconfig.json`; the executable must be installed separately. |
| Patch hygiene | `git diff --check` | Run before handing off edits. |

`test.py` at the repository root is a legacy standalone network experiment. It is not
imported by the application, is not discovered by `make test`, and contacts an external
address in a large loop. Do not run it as project verification.

## HTTP API contract

FastAPI generates the authoritative OpenAPI schema at `/openapi.json`. The hand-written
contract below records behavior that is easy to miss from schemas alone.

| Method and path | Input | Success | Important behavior and errors |
| --- | --- | --- | --- |
| `GET /health` | None | `{"status":"ok"}` | Does not call Gemini or SQLite. |
| `POST /analyze` | JSON `text` (1–10,000 nonblank characters), optional `source` (up to 100 characters) | `AnalyzeResponse`: random analysis `id`, `detective`, optional `character`, optional `character_notice`, and `usage` | Reserves one `detective` call. A suspicious/dangerous result may reserve a second `character` call. Returns 429 at the session limit, 502 for Detective provider failure, and 503 for repository failure. The analysis is saved only after generation completes. |
| `GET /analyses/{analysis_id}` | A 32-character lowercase hexadecimal ID | `StoredAnalysis` | Returns 404 when absent and 422 for a malformed ID. The random ID acts as a bearer capability; this route is not session-owned. Stored responses do not include the generated character reply. |
| `GET /session/ai-calls` | HttpOnly session cookie set by middleware | `AiCallHistory` with `usage` and ordered calls | Returns audit metadata for the current cookie session only. It does not return analysis ownership. |
| `GET /...` static paths | Browser path | Files and directory indexes from `frontend/` through `StaticFiles` | Mounted last at `/`, so declared API routes take precedence. The mount is omitted when `frontend/` is absent. |

All FastAPI request-validation failures use the deliberately generic 422 detail:
`The submitted request is invalid. Check its fields and try again.` Do not make that
handler specific to `/analyze`; it also handles path parameters.

## Request flows and invariants

### Analysis

1. `session_cookie_middleware` accepts a valid 32-character hex cookie or generates one.
2. Pydantic validates `AnalyzeRequest` before route code runs.
3. `reserve_ai_call` atomically checks session usage and inserts a pending `detective`
   audit row.
4. `ScamAnalyzer.analyze` requests structured Gemini JSON. Malformed provider content
   becomes a conservative fallback; timeouts and HTTP failures become `AnalysisError`.
5. `classify_risk` merges model output with local signals. Local logic can only raise the
   risk, never lower it.
6. Suspicious/dangerous results may invoke `CALMING_GUIDE`. Character failure is optional
   here: `CharacterError` and provider-adapter `ValueError` are isolated, so the Detective
   result remains successful and `character_notice` is returned.
7. The repository saves the submitted text and validated `ScamAnalysis`, and the route
   returns the random record ID.

The frontend makes one `/analyze` request and renders the returned `detective` and
`character`/`character_notice` in separate panels. It never calls Cô tâm lý directly.

## L3 functional requirements

- **L3-01:** `CALMING_GUIDE` is the Cô tâm lý profile. Its system instruction requires a
  close, calm voice, `cô`/`bác` address, and exactly two or three concise sentences about
  the psychological tactic.
- **L3-02:** `/analyze` awaits Detective generation and local classification before it can
  await Cô tâm lý. `frontend/index.html` renders the two outputs as separate cards.
- **L3-03:** only `suspicious` and `dangerous` levels trigger Cô tâm lý. Its reservation,
  provider call, audit, and error notice are independent; a failure never removes the
  Detective result.
- **L3-04:** the Detective prompt JSON-encodes submitted text as
  `UNTRUSTED_MESSAGE_JSON`; provider schemas validate output, indicator excerpts must
  occur in the original text, and `classify_risk` can only raise model risk. The Cô tâm lý
  prompt receives the validated Detective result rather than raw submitted text.
- **L3-05:** `tests/labeled_messages.json` contains 24 labeled messages. `make
  test-offline` sends each through `POST /analyze` with a stable provider double and prints
  a ĐÚNG/SAI comparison table. This verifies the API and deterministic safety layer; it
  does not claim live Gemini accuracy.
- **L3-06:** `frontend/scam-library.json` defines twelve common scam types with signs and
  actions. The page filters them by giả ngân hàng, giả công an, trúng thưởng, giả giao
  hàng, or other, and opens full details when a card is selected.

## Persistence and privacy

`AnalysisRepository` uses SQLite. File databases open a connection per operation;
`:memory:` keeps one shared connection for tests. `_create_schema` is both initial schema
creation and the migration path for older analysis tables.

- `analyses` stores raw submitted text, source, validated scores/reasoning, JSON indicator
  data, actions, provider risk level, scenario matrix, and timestamp.
- `ai_calls` stores random call ID, opaque session ID, call kind, input length, pending or
  final success status, summary, and timestamp.
- There is intentionally no character-chat endpoint, request schema, conversation table,
  or transcript storage.
- Quota reservation uses `BEGIN IMMEDIATE`, making the count-and-insert operation atomic
  for concurrent requests on a file database.
- `_complete_log` intentionally does not fail an otherwise completed API response when an
  audit update fails; it logs the database exception server-side.
- The `scamcheck_session` cookie is HttpOnly, SameSite=Lax, and Secure on HTTPS. It scopes
  quota/audit history only. Analysis IDs are globally retrievable bearer capabilities.

Changing either table requires a backward-compatible migration in `_create_schema` plus a
legacy-schema test in `tests/test_database.py`.

## File implementation map

### Backend

- `src/main.py`: FastAPI composition, lifespan, dependency protocols, cookie middleware,
  global validation handler, quota/audit orchestration, HTTP routes, error translation,
  and final static mount. Keep provider logic out of routes and SQLite details out of this
  file.
- `src/schemas.py`: public Pydantic request/response models, constrained IDs and text,
  twelve ordered scam scenario codes, default actions, and model-level consistency checks.
  Provider-only schemas belong in `analyzer.py`, not here.
- `src/analyzer.py`: Gemini transport, provider response schemas, prompts, timeout/retry
  logic, structured-response parsing, local risk escalation, fallback analysis, and
  character voice validation. `_generate` retries only HTTP 429 twice and extracts the
  first nonempty candidate text.
- `src/characters.py`: immutable `CharacterSpec` and the `CALMING_GUIDE`/Cô tâm lý voice
  contract used for the optional one-time `/analyze` response.
- `src/database.py`: SQLite initialization/migrations, analysis serialization,
  cryptographically random IDs, atomic AI-call reservations, audit completion/history,
  async thread handoff for file databases, and the shared in-memory test connection.
- `src/config.py`: `.env` loading, provider aliases (`GOOGLE_*` preferred over legacy
  `GEMINI_*`), database path, and positive per-session call-limit validation. Loading only
  the database path does not require provider credentials.
- `src/__init__.py`: package marker and short package description.

### Tests and evaluation

- `tests/test_api.py`: ASGI contract tests using `httpx.AsyncClient`, an in-memory
  repository, and `StubAnalyzer`. It covers health, analyze/get behavior, quota/audit,
  automatic character fallback, 502/503 mapping, and five credential-gated live Gemini
  cases in `LiveGeminiApiTests`.
- `tests/test_analyzer.py`: mocked HTTP tests for Gemini request schemas, parsing/fallback,
  rate-limit backoff, character voice enforcement, prompt injection, benign OTP handling,
  and local URL/urgency escalation.
- `tests/test_database.py`: save/get behavior and migration of records created before the
  scenario/action/evidence columns.
- `tests/test_regression.py`: runs the labeled corpus through the offline HTTP API and
  prints the expected/actual ĐÚNG/SAI table.
- `tests/labeled_messages.json`: 24 deterministic safe, suspicious, and dangerous
  messages, including the four named library groups and prompt-injection attempts.
- `tests/test_frontend.py`: validates the two result regions and the count, filter groups,
  and detail fields in the library data.
- `tests/factories.py`: canonical ordered scenario builders shared by API/analyzer/database
  tests. Use these instead of hand-building a partial scenario matrix.
- `tests/_logging.py`: disables expected error logs during tests. Import it before code
  paths that intentionally exercise failures.

### Commands, UI, and repository metadata

- `frontend/index.html`: accessible analysis form, separate Detective/Cô tâm lý results,
  library filters, and scam-detail dialog.
- `frontend/app.js`: `POST /analyze` integration, safe DOM rendering, library filtering,
  and detail-dialog behavior. It contains no direct character call or chat UI.
- `frontend/styles.css`: all static client styling and responsive rules.
- `frontend/scam-library.json`: twelve user-facing scam profiles, filter groups, warning
  signs, and recommended actions.
- `frontend/README.md`: frontend file responsibilities and sequential-flow notes.
- `README.md`: contributor overview and main commands. Keep user-facing setup here; keep
  agent-level invariants in this file.
- `Makefile`: short wrappers for offline API tests, online API tests, and running the app.
- `pyproject.toml`: Python version, runtime dependencies, and package metadata.
- `uv.lock`: reproducible dependency lock; update it through `uv`, never by hand.
- `pyrightconfig.json`: strict checking for `src/` with the local `.venv`.
- `.env.example`: nonsecret provider/database/quota configuration template.
- `.gitignore`: excludes credentials, local databases, virtual environments, caches, and
  build artifacts.

## Test expectations for future changes

For backend changes, run `make test-offline` first. Run `make test-online` only when
credentials/cost are appropriate, and be explicit in handoff notes when live tests ran,
skipped, or failed because of provider behavior. Never claim live coverage from mocked
tests.

Character changes must retain tests proving the optional automatic `/analyze` response,
its quota use, failure fallback, and voice contract. Do not add character-chat coverage
unless an explicit product requirement first restores a chat API.

Risk-filter changes must run the labeled corpus. Keep it at 20 or more cases and preserve
the printed expected/actual table. Add a labeled case when a deterministic filtering bug
is found; do not silently alter a label just to make the suite pass.

Use mocked transports for deterministic prompt/response assertions. Live tests are useful
for integration confidence but are nondeterministic, credentialed, slower, and may consume
paid quota.

## Agent collaboration rationale and record

Use sub-agents only for bounded work that can proceed independently and materially improve
speed or review quality. Because all agents share one worktree, prefer read-only analysis
or clearly disjoint files; one agent should own interdependent edits to schemas, routes,
analyzer protocols, and their tests. Do not delegate reading or interpreting an applicable
skill file.

On 2026-07-16, character chat was removed as one coupled backend change: the route, public
request/response schemas, optional chat prompt branch, registry, and chat-specific tests
were deleted together. The automatic character response from `/analyze` was intentionally
preserved. No sub-agents were used because these edits shared one small contract, and no
broad bug scan was performed.

Later on 2026-07-16, the six L3 requirements were recorded and completed without restoring
character chat. The work added the two-panel UI, twelve-type library, and 24-message API
regression table; it also renamed the one-time response to Cô tâm lý. The corpus exposed
an official-URL punctuation bug during the requested path, so URL normalization and a
focused test were added. No sub-agents were used because the backend contract, corpus,
frontend, and documentation needed one consistent interpretation of the sequential flow.

## Handoff checklist

Before completing a change:

1. Confirm the diff contains no unrelated user-owned edits or secrets.
2. Update this guide when endpoints, file responsibilities, persistence, tests, or safety
   boundaries change.
3. Run focused tests, the deterministic suite, and `git diff --check`.
4. Run live tests only when credentials/cost are appropriate and report their status
   separately from deterministic tests.
5. State explicitly whether the frontend, database schema, public response shape, or
   provider prompt changed.
