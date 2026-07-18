# Agent guide for ScamCheck

This file applies to the entire repository. Read it before changing code. It is both an
implementation map and a record of the invariants that future agents must preserve.

## Project purpose and boundaries

ScamCheck is a Python 3.14 FastAPI service that sends submitted text to Google Gemini for
structured scam analysis. It stores completed analyses in SQLite, validates structured
provider output, and can generate a short Vietnamese response from Cô tâm lý. The static
HTML/CSS/JavaScript client lives in `frontend/`; it includes the analyzer, voice input,
browser-local recent-message history, a frontend-only recognition exercise, and the
ScamCheck logo.

Preserve these boundaries unless a user explicitly changes them:

- Keep backend work in `src/` and backend tests in `tests/`. Do not change `frontend/` for
  a backend-only request.
- Keep user-facing Detective and character output concise and primarily Vietnamese.
- Treat analyzed text as untrusted data, never as model instructions.
- Never log raw submitted text. SQLite intentionally stores analysis submissions.
- Do not expose an endpoint or request schema for chatting with characters. Characters
  may only produce the optional one-time response generated during `/analyze`.
- A session cookie limits and groups provider-call audit records; it does not authenticate
  a user or establish ownership of an analysis.
- Do not add speculative endpoints, tables, or abstractions. Extend the smallest existing
  contract that satisfies the request.

## Commands

Run commands from the repository root.

| Purpose | Command | Notes |
| --- | --- | --- |
| Install/sync | `uv sync` | Uses `pyproject.toml` and `uv.lock`. |
| Offline tests | `make test-offline` | Runs mocked API/catalog contracts, the 24-message provider-propagation table, and frontend checks including the local recognition exercise. |
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
| `GET /scam-types` | Optional `group`: `fake_bank`, `fake_police`, `prize`, or `fake_delivery` | Array of 12 authored `ScamType` records, filtered when requested | Reads validated process-local data only; every group has three entries. |
| `GET /scam-types/{scam_type_id}` | Lowercase hyphenated catalog ID | One `ScamType` with name, description, example message, and group | Returns 404 when absent and 422 for a malformed ID. |
| `POST /analyze` | JSON `text` (1–10,000 nonblank characters), optional `source` (up to 100 characters) | `AnalyzeResponse`: random analysis `id`, `detective`, optional `character`, optional `character_notice`, and `usage` | Atomically reserves and audits one `detective` call under the configured session limit. A suspicious/dangerous result may reserve a second `character` call. Returns 429 without calling Gemini when no slot remains, 502 for Detective provider failure, and 503 for repository failure. The analysis is saved only after generation completes. |
| `GET /analyses/{analysis_id}` | A 32-character lowercase hexadecimal ID | `StoredAnalysis` | Returns 404 when absent and 422 for a malformed ID. The random ID acts as a bearer capability; this route is not session-owned. Stored responses do not include the generated character reply. |
| `GET /session/ai-calls` | HttpOnly session cookie set by middleware | `AiCallHistory` with authoritative `used`/`limit` usage and ordered calls | Returns audit metadata for the current cookie session only. It does not return analysis ownership. |
| `GET /` | None | `frontend/index.html` | Registered when the file exists; it does not expose other repository files. |
| `GET /styles.css` | None | `frontend/styles.css` | Explicit stylesheet route; no directory mount or listing. |
| `GET /app.js` | None | `frontend/app.js` | Explicit JavaScript route; no directory mount or listing. |
| `GET /offline-analyzer.js` | None | `frontend/offline-analyzer.js` | Conservative browser-only fallback used when the browser reports no connection. |
| `GET /service-worker.js` | None | `frontend/service-worker.js` | Caches only the five authored shell assets for offline loading; it never intercepts API routes. |
| `GET /scamcheck-logo.png` | None | `frontend/scamcheck-logo.png` | Explicit PNG route; the repository and other frontend files are never exposed as a static directory. |

All FastAPI request-validation failures use the deliberately generic 422 detail:
`The submitted request is invalid. Check its fields and try again.` Do not make that
handler specific to `/analyze`; it also handles path parameters.

## Request flows and invariants

### Analysis

1. `session_cookie_middleware` accepts a valid 32-character hex cookie or generates one.
2. Pydantic validates `AnalyzeRequest` before route code runs.
3. `reserve_ai_call` atomically checks the configured session limit, inserts a pending
   `detective` audit row when a slot remains, and returns authoritative `used`/`limit`
   usage. A full session receives 429 without a provider call.
4. `ScamAnalyzer.analyze` requests structured Gemini JSON. Malformed provider content
   becomes a conservative fallback; timeouts and HTTP failures become `AnalysisError`.
5. The validated provider `risk_level` becomes the Detective risk unchanged. If malformed
   provider content triggers the conservative fallback, its risk is `suspicious`.
6. Suspicious/dangerous results may invoke `CALMING_GUIDE`. Character failure is optional
   here: `CharacterError` and provider-adapter `ValueError` are isolated, so the Detective
   result remains successful and `character_notice` is returned.
7. The repository saves the submitted text and validated `ScamAnalysis`, and the route
   returns the random record ID.

When online, the frontend makes one checking request to `/analyze` and renders the returned
`detective` and `character`/`character_notice` in separate panels. It never calls Cô tâm lý
directly.
Provider evidence and raw submitted text are rendered with DOM text nodes, never as active
links or HTML. The page also reads `/session/ai-calls` to display authoritative
`used`/`limit` usage and disables submission after the session reaches its ceiling.

The cancel button aborts only the browser's wait. The provider/database operation may
already have started and its audit reservation may still be counted, so the page states
that caveat and refreshes usage. A successful submission is added to a ten-item
localStorage history; deleting that browser-local copy does not delete the SQLite
analysis. The persistent top navigation uses `#analyze`, `#history`, and `#practice` views.
History is a dedicated page rather than a dialog; its “Kiểm tra lại” action copies a local
message into the analysis composer without calling an API. New history entries store a
bounded snapshot of the displayed risk, reasoning, evidence, actions, Cô tâm lý text, and
online/offline mode. “Xem kết quả” converts that snapshot into the existing full result
renderer without regenerating it; legacy message-only entries remain supported but clearly
show that no result was saved.

The service worker caches `/`, `/styles.css`, `/offline-analyzer.js`, `/app.js`, and
`/scamcheck-logo.png` after a successful online visit. When the browser reports that it is
offline, `offline-analyzer.js` performs a conservative rule-based assessment on the device
and labels it as preliminary. It does not call Gemini, consume quota, write SQLite, or claim
provider accuracy. API responses, submitted text, analysis results, and session usage are
never added to the offline cache. A zero-signal offline result must still warn that it
cannot establish safety.

### Catalog

- The four required scam groups and twelve authored records live in
  `src/data/scam_types.json`; do not duplicate a client-side catalog.
- `src/catalog.py` validates catalog data at import and owns filtering and detail lookup.
- Online link and message assessment belongs to the provider-backed `/analyze` call. The
  browser's offline analyzer is a deliberately limited fallback and must not alter online
  provider results.

### Frontend recognition exercise

- The ten authored prompts, balanced `scam`/`safe` labels, and explanations live only in
  `frontend/app.js`.
- The browser displays one prompt at a time and reveals its label and explanation only
  after the user chooses an answer.
- Grading and score state run in page memory. They do not call an API or Gemini and are
  not stored in localStorage, SQLite, or the session cookie.
- There is intentionally no `/practice-messages` backend endpoint or public practice
  schema.

## L3 functional requirements

- **L3-01:** `CALMING_GUIDE` is the Cô tâm lý profile. Its system instruction requires a
  close, calm voice, `cô`/`bác` address, and exactly two or three concise sentences about
  the psychological tactic.
- **L3-02:** `/analyze` awaits and validates Detective generation before it can await Cô
  tâm lý. `frontend/index.html` renders the two outputs in separate result sections.
- **L3-03:** only `suspicious` and `dangerous` levels trigger Cô tâm lý. Its reservation,
  provider call, audit, and error notice are independent; a failure never removes the
  Detective result.
- **L3-04:** the Detective prompt JSON-encodes submitted text as
  `UNTRUSTED_MESSAGE_JSON`; provider schemas validate output, indicator excerpts must
  occur in the original text, and the validated provider risk is authoritative. The Cô
  tâm lý prompt receives the validated Detective result rather than raw submitted text.
- **L3-05:** `tests/labeled_messages.json` contains 24 labeled messages. `make
  test-offline` sends each through `POST /analyze` with a stable provider double and prints
  a ĐÚNG/SAI comparison table. The double supplies the authored risk label, so this verifies
  API propagation and does not claim live Gemini accuracy.
- **L3-06:** `src/data/scam_types.json` defines twelve common scam types across the four
  required groups. `/scam-types` filters server-side and `/scam-types/{id}` loads one
  authored detail record without invoking Gemini.

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
- AI-call quota reservation uses `BEGIN IMMEDIATE`, making the limit-check-and-insert
  operation atomic for concurrent requests on a file database.
- `_complete_log` intentionally does not fail an otherwise completed API response when an
  audit update fails; it logs the database exception server-side.
- The `scamcheck_session` cookie is HttpOnly, SameSite=Lax, and Secure on HTTPS. It scopes
  audit history only. Analysis IDs are globally retrievable bearer capabilities.

Changing either table requires a backward-compatible migration in `_create_schema` plus a
legacy-schema test in `tests/test_database.py`.

## File implementation map

### Backend

- `src/main.py`: FastAPI composition, lifespan, dependency protocols, cookie middleware,
  global validation handler, AI-call audit orchestration, HTTP routes, error translation,
  and the six explicit frontend asset routes. Keep provider logic out of routes and SQLite
  details out of this file.
- `src/schemas.py`: public Pydantic request/response models, constrained IDs and text,
  catalog contracts, twelve ordered scam scenario codes, default actions, and model-level
  consistency checks. Provider-only schemas belong in `analyzer.py`, not here.
- `src/analyzer.py`: Gemini transport, provider response schemas, prompts, timeout/retry
  logic, structured-response validation, fallback analysis, and character voice
  validation. `_generate` retries only HTTP 429 twice and extracts the first nonempty
  candidate text.
- `src/catalog.py`: validated static catalog access and filtering.
- `src/data/scam_types.json`: twelve authored scam types; exactly three entries in each of
  the four required groups, with name, description, example message, and group.
- `src/characters.py`: immutable `CharacterSpec` and the `CALMING_GUIDE`/Cô tâm lý voice
  contract used for the optional one-time `/analyze` response.
- `src/database.py`: SQLite initialization/migrations, analysis serialization,
  cryptographically random IDs, atomic AI-call reservations, audit completion/history,
  async thread handoff for file databases, and the shared in-memory test connection.
- `src/config.py`: `.env` loading, provider aliases (`GOOGLE_*` preferred over legacy
  `GEMINI_*`), database path, and positive `AI_SESSION_CALL_LIMIT` validation. Loading only
  the database path does not require provider credentials.
- `src/__init__.py`: package marker and short package description.

### Tests and evaluation

- `tests/test_api.py`: ASGI contract tests using `httpx.AsyncClient`, an in-memory
  repository, and `StubAnalyzer`. It covers health, catalog APIs, analyze/get behavior,
  the absence of a practice API, session quota/auditing, automatic character fallback,
  429/502/503 mapping, and five credential-gated live Gemini cases in
  `LiveGeminiApiTests`.
- `tests/test_analyzer.py`: mocked HTTP tests for Gemini request schemas, parsing/fallback,
  rate-limit backoff, character voice enforcement, and prompt injection isolation.
- `tests/test_database.py`: save/get behavior and migration of records created before the
  scenario/action/evidence columns.
- `tests/test_config.py`: default, override, and invalid session-call-limit configuration.
- `tests/test_catalog.py`: catalog size, required fields, and group balance.
- `tests/test_regression.py`: runs the labeled corpus through the offline HTTP API and
  prints the expected/actual ĐÚNG/SAI table.
- `tests/labeled_messages.json`: 24 deterministic safe, suspicious, and dangerous
  messages, including the four named library groups and prompt-injection attempts.
- `tests/test_frontend.py`: validates that the root page calls the analysis and usage
  APIs online; renders Detective/Cô tâm lý separately; keeps the balanced practice dataset
  and grading in the browser; wires the explicitly preliminary offline analyzer; and keeps
  analysis, local history, and practice in separate hash-routed views.
- `tests/factories.py`: canonical ordered scenario builders shared by API/analyzer/database
  tests. Use these instead of hand-building a partial scenario matrix.
- `tests/_logging.py`: disables expected error logs during tests. Import it before code
  paths that intentionally exercise failures.

### Commands, UI, and repository metadata

- `frontend/index.html`: accessible application shell with persistent top navigation,
  separate analysis/history/practice views, result/processing states, connectivity notice,
  and references to the browser assets.
- `frontend/styles.css`: mobile-first page styling, the automatic 900px+ widescreen
  analysis workspace, responsive navigation and result/history/practice layouts, focus
  states, and reduced-motion behavior.
- `frontend/app.js`: `/analyze` integration, AI-call `used`/`limit` display and limit-state
  handling, safe result rendering,
  voice input, cancellation, browser-local recent-message history, and the local
  recognition prompts/grading/score. It registers the offline shell service worker and
  routes offline submissions through the local analyzer, owns hash-based view switching,
  and supports reusing a history item in the composer. It contains no direct character API
  call or chat UI.
- `frontend/offline-analyzer.js`: conservative, browser-only rules that return a compatible
  preliminary risk result without network, quota, cookie, or database access. It is not
  used to override a Gemini result.
- `frontend/service-worker.js`: versioned cache for the root page, stylesheet, browser
  scripts, and logo only. It does not intercept or cache API requests or user data.
- `frontend/scamcheck-logo.png`: the only standalone visual asset used by the page.
- `README.md`: contributor overview and main commands. Keep user-facing setup here; keep
  agent-level invariants in this file.
- `Makefile`: short wrappers for offline API tests, online API tests, and running the app.
- `pyproject.toml`: Python version, runtime dependencies, and package metadata.
- `uv.lock`: reproducible dependency lock; update it through `uv`, never by hand.
- `pyrightconfig.json`: strict checking for `src/` with the local `.venv`.
- `.env.example`: nonsecret provider and database configuration template.
- `.gitignore`: excludes credentials, local databases, virtual environments, caches, and
  build artifacts.

## Test expectations for future changes

For backend changes, run `make test-offline` first. Run `make test-online` only when
credentials/cost are appropriate, and be explicit in handoff notes when live tests ran,
skipped, or failed because of provider behavior. Never claim live coverage from mocked
tests.

Character changes must retain tests proving the optional automatic `/analyze` response,
its audit record, failure fallback, and voice contract. Do not add character-chat
coverage unless an explicit product requirement first restores a chat API.

Risk-contract changes must run the labeled corpus. Keep it at 20 or more cases and
preserve the printed expected/actual table. The offline provider double supplies authored
labels; only live tests can provide evidence about Gemini accuracy.

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

The later backend catalog/link change moved the twelve-type catalog from a static frontend
file to `src/data`, added read-only catalog and link-inspection APIs, and introduced the
balanced ten-message data file. The existing UI was adapted to consume these APIs through
hash routing. No sub-agents were used because data schemas, URL safety semantics, API
responses, and client navigation formed one contract; no unrelated bug scan was done.

The practice/share-image change reused `src/data/sample_messages.json`: the backend now
projects answer-free prompts and grades individual guesses, while the browser owns score
state and immediate feedback. The same client draws analysis summaries through Canvas at
1080×1080. No database or AI contract was added, and no sub-agents were used because the
grading response, client state machine, routing, and tests were tightly coupled.

On 2026-07-17, the supplied root-level `index.html` replaced the deleted `frontend/`
bundle and was integrated with the existing backend. Its browser-only regex simulation
was removed: the page now calls local link inspection before `/analyze`, renders the
validated Detective/Cô tâm lý response and quota, and aborts its wait without claiming to
cancel an already-started provider call. FastAPI serves only the root HTML and logo rather
than mounting the repository as a static directory. No sub-agents were used because the
page request flow, response rendering, static routes, and integration tests were one
coupled contract.

Later on 2026-07-17, the integrated page and logo were moved back under `frontend/` to
separate UI assets from backend and repository-root files. The public browser paths stayed
`/` and `/scamcheck-logo.png`; FastAPI still serves only those two explicit files rather
than mounting the directory. No sub-agents were used because this was one path-only
refactor across the assets, route configuration, tests, and documentation.

The frontend split later that day moved inline CSS and JavaScript from
`frontend/index.html` into `frontend/styles.css` and `frontend/app.js`. FastAPI gained
explicit `/styles.css` and `/app.js` routes while retaining the no-directory-mount
boundary. No frontend behavior, API response, persistence, or provider prompt changed,
and no sub-agents were used because the extraction and serving contract were tightly
coupled.

Later on 2026-07-17, deterministic backend checking was removed at the user's request.
The keyword/URL risk escalation function, local `/links/inspect` endpoint and schemas,
domain parser, and frontend link-inspection call were deleted together. `/analyze` now
propagates the validated Gemini `risk_level` unchanged, except that malformed provider
content still uses the existing conservative `suspicious` fallback. The database schema
and provider prompts did not change. No sub-agents were used because the route, schemas,
analyzer behavior, frontend sequence, regression double, and documentation formed one
contract.

The frontend later gained an automatic widescreen mode at 900px without changing its
mobile-first markup behavior or JavaScript flow. Desktop input controls use a two-column
workspace, result evidence uses two columns, recommendations use three columns, and the
history panel widens. The API, persistence, and provider contracts did not change.

The per-session AI call limit was later removed while retaining session-scoped call
auditing. Reservations no longer reject calls, `AI_SESSION_CALL_LIMIT` was removed from
configuration, and public usage objects now contain only the total `used` count. The
frontend reports that count without presenting a remaining allowance. The AI audit table,
analysis schema, and provider prompts did not change.

On 2026-07-18, the per-session AI resource ceiling was restored. The default allowance is
10 provider calls per cookie session and can be changed with `AI_SESSION_CALL_LIMIT`.
Detective and character calls each consume one reservation; SQLite rejects reservations
atomically at the ceiling, `/analyze` returns a polite 429 before contacting a provider,
and usage responses contain both `used` and `limit`. The frontend displays the fraction
and disables analysis at the ceiling. Existing per-call timeouts remain 12 seconds for
the Detective and 6 seconds for the character.

The recognition exercise was then integrated into the current frontend and moved fully
out of the backend at the user's request. Its ten prompts, labels, explanations, grading,
and page-memory score now live in `frontend/app.js`; the practice routes, public schemas,
catalog helpers, backend sample data, and API tests were removed. The exercise makes no
network, Gemini, SQLite, cookie, or localStorage call. The analysis API, database schema,
and provider prompts did not change.

The offline continuation first added a narrowly scoped service worker, then was clarified
by the user to require actual message analysis without connectivity. The browser now uses
a conservative local rules engine only while offline and clearly labels its output as
preliminary; online analysis remains provider-backed and authoritative. No API response or
submitted text is cached, and offline results do not consume quota or reach SQLite. The
database schema, public response shapes, and provider prompts did not change.

The later UI/UX refactor replaced the stacked analysis/practice page and history overlay
with a persistent three-item top navigation. Analysis, browser-local history, and practice
are independent hash-routed views; history items can be copied back into the composer.
Mobile remains single-column while desktop uses a focused analysis workspace and compact
result grids. No API, provider prompt, database schema, offline rule, or public response
shape changed.

History review was then extended without changing the server contract. Each successful
browser submission stores a bounded local snapshot of the result shown at that time:
message, risk status, confidence, reasoning, up to four evidence items, three actions,
Cô tâm lý text, and Gemini/offline mode. The History view reopens this snapshot in the
existing full result screen without an API call, and keeps compatibility with older
message-only entries. Legacy entries clearly show that no saved result is available and can
still be rechecked. No result is regenerated, and the database schema, public response
shapes, provider prompts, and offline rules did not change.

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
