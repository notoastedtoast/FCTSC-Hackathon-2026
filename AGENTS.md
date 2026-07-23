# Agent guide for ScamCheck

This file applies to the entire repository. Read it before changing code. It is both an
implementation map and a record of the invariants that future agents must preserve.

## Project purpose and boundaries

ScamCheck is a Python 3.14 FastAPI service that sends submitted text through an ordered
Gemini/Groq provider chain for structured scam analysis. It stores completed analyses in
local SQLite by default or Supabase PostgreSQL when configured, validates structured provider output, runs advisory deterministic
text/domain checks, and can generate a short Vietnamese response from Cô tâm lý. The
static HTML/CSS/JavaScript client lives in `frontend/`; it includes the analyzer, voice
input, server-backed online history, bounded browser-local offline history, a frontend-only
recognition exercise, and the ScamCheck logo.

Preserve these boundaries unless a user explicitly changes them:

- Keep backend work in `src/` and backend tests in `tests/`. Do not change `frontend/` for
  a backend-only request.
- Keep user-facing Detective and character output concise and primarily Vietnamese.
- Treat analyzed text as untrusted data, never as model instructions.
- Never log raw submitted text. The configured database intentionally stores analysis submissions.
- Do not expose an endpoint or request schema for chatting with characters. AI-generated
  character output is limited to the optional one-time Cô tâm lý response generated during
  `/analyze`; the frontend-only Người ứng cứu uses authored action lists and makes no provider call.
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
| Online API tests | `make test-online` | Runs the credential-gated live provider tests in `tests.test_live_api`. |
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
| `GET /health` | None | `{"status":"ok"}` | Does not call Gemini or the database. |
| `GET /scam-types` | Optional `group`: `fake_bank`, `fake_police`, `prize`, or `fake_delivery` | Array of 12 authored `ScamType` records, filtered when requested | Reads validated process-local data only; every group has three entries. |
| `GET /scam-types/{scam_type_id}` | Lowercase hyphenated catalog ID | One `ScamType` with name, description, example message, and group | Returns 404 when absent and 422 for a malformed ID. |
| `POST /analyze` | JSON `text` (1–10,000 nonblank characters), optional `source` (up to 100 characters), and optional `X-ScamCheck-Request-ID` header | `AnalyzeResponse`: random analysis `id`, `detective`, optional `character`, optional `character_notice`, advisory `deterministic_findings`, and `usage` | A valid request ID makes manual reconnect retries idempotent within the cookie session: a completed retry replays the original response, a still-pending retry returns 409 with `Retry-After`, and reusing the ID for different content returns 409. A newly claimed request atomically reserves and audits one `detective` call under the configured session limit. A suspicious/dangerous result may reserve a second `character` call. Returns 429 without calling a provider when no slot remains, a safe Vietnamese 502 detail only after every configured Detective target fails, and 503 for repository failure. The analysis is saved only after generation completes. |
| `GET /analyses/{analysis_id}` | A 32-character lowercase hexadecimal ID | `StoredAnalysis` | Returns 404 when absent and 422 for a malformed ID. The random ID acts as a bearer capability; this route is not session-owned. Stored responses do not include the generated character reply. |
| `GET /session/ai-calls` | HttpOnly session cookie set by middleware | `AiCallHistory` with authoritative `used`/`limit` usage and ordered calls | Returns audit metadata for the current cookie session only. It does not return analysis ownership. |
| `GET /history/` | HttpOnly session cookie set by middleware | Up to ten completed `HistoryEntry` records | Returns only replayable online results created in the current cookie session. Character output is read from the cached idempotent response and is not regenerated. |
| `DELETE /history/{analysis_id}` | A 32-character lowercase hexadecimal analysis ID plus the session cookie | Empty 204 response | Hides the matching result from the current session's history without deleting its analysis or idempotency record; returns 404 when it is absent or belongs to another session. |
| `GET /` | None | `frontend/index.html` | Registered when the file exists; it does not expose other repository files. |
| `GET /styles.css` | None | `frontend/styles.css` | Explicit stylesheet route; no directory mount or listing. |
| `GET /app.js` | None | `frontend/app.js` | Explicit JavaScript route; no directory mount or listing. |
| `GET /offline-analyzer.js` | None | `frontend/offline-analyzer.js` | Conservative browser-only fallback used when the browser reports no connection. |
| `GET /service-worker.js` | None | `frontend/service-worker.js` | Caches only the eight authored shell assets for offline loading; it never intercepts API routes. Core UI files use network-first refresh with cached fallback. |
| `GET /scamcheck-logo.png` | None | `frontend/scamcheck-logo.png` | Explicit PNG route; the repository and other frontend files are never exposed as a static directory. |
| `GET /detective-avatar.png` | None | `frontend/detective-avatar.png` | Explicit PNG route for the Detective result-message avatar; no frontend directory is mounted. |
| `GET /psychologist-avatar.png` | None | `frontend/psychologist-avatar.png` | Explicit PNG route for the Cô tâm lý result-card avatar; no frontend directory is mounted. |
| `GET /responder-avatar.png` | None | `frontend/responder-avatar.png` | Explicit PNG route for the frontend-only Người ứng cứu profile and message avatar; no frontend directory is mounted. |

All FastAPI request-validation failures use the deliberately generic 422 detail:
`The submitted request is invalid. Check its fields and try again.` Do not make that
handler specific to `/analyze`; it also handles path parameters.

## Request flows and invariants

### Analysis

1. `session_cookie_middleware` accepts a valid 32-character hex cookie or generates one.
2. Pydantic validates `AnalyzeRequest` before route code runs.
3. The route uses the supplied request ID, or generates one for a request that omitted the
   header, then claims its session-scoped content hash before quota is used. A supplied ID
   makes manual retry stable: completed retries replay the saved response, while pending
   retries return 409 with `Retry-After` without another provider call.
4. `reserve_ai_call` atomically checks the configured session limit, inserts a pending
   `detective` audit row when a slot remains, and returns authoritative `used`/`limit`
   usage. A full session receives 429 without a provider call.
5. `ScamAnalyzer.analyze` tries the primary Gemini model, the secondary Gemini model, then
   Groq when `GROQ_API_KEY` is configured. A deadline-aware weighted allocation gives every
   remaining target a bounded share and carries unused time forward without exceeding the
   total timeout. Groq uses strict JSON Schema (all object fields required and closed) and a
   minimum completion budget. HTTP errors, timeouts, missing content, and schema-invalid
   output advance immediately without retry sleeps. Safe logs include provider/model,
   elapsed/allocated time, HTTP status or validation locations, but never prompt, generated
   content, submitted text, or credentials. If every transport fails the call becomes
   `AnalysisError`; if at least one target responds but all responses are malformed,
   Detective uses the conservative suspicious fallback.
6. The validated provider `risk_level` becomes the Detective risk unchanged. If malformed
   provider content across the chain triggers the conservative fallback, its risk is
   `suspicious`.
7. `src/deterministic_checker.py` runs concurrently as bounded supporting analysis. Its
   text, known-shortener, lookalike, punycode, and Cyrillic findings are returned for the
   UI, but its compatibility `risk_floor` never overrides the provider risk. The normal
   request path does not contact submitted URLs or shortening services.
8. Suspicious/dangerous results may invoke `CALMING_GUIDE`. Character failure is optional
   here: `CharacterError` and provider-adapter `ValueError` are isolated, so the Detective
   result remains successful and `character_notice` is returned.
9. The repository saves the submitted text and validated `ScamAnalysis`. For an
   idempotent request, the analysis and replayable response are committed atomically.

When online, the frontend makes one checking request to `/analyze` and renders the returned
`detective` and `character`/`character_notice` in separate panels. The Cô tâm lý panel is
hidden for `safe` results and shown only for `suspicious` or `dangerous` results. The
frontend never calls Cô tâm lý directly.
Provider evidence and raw submitted text are rendered with DOM text nodes, never as active
links or HTML. The original message is the Detective's second sequential bubble. Exact
provider excerpts are highlighted there only for
`suspicious` or `dangerous` results; safe messages show no warning highlight or highlight
note. The three recommended actions form the Detective's final sequential bubble, and the
Cô tâm lý section is revealed only after that bubble finishes. Newly revealed Detective
and Cô tâm lý bubbles auto-scroll into view while follow mode is active. An upward user
scroll pauses follow mode and exposes a down-arrow control that resumes it. The page also reads
`/session/ai-calls` to display authoritative
`used`/`limit` usage and disables submission after the session reaches its ceiling.
Detective, Cô tâm lý, and Người ứng cứu rows are genuinely unhidden one at a time at
one-second intervals rather than rendering a complete block with only delayed styling.
Cô tâm lý emoji are selected from each sentence's meaning. Detective evidence omits
repetitive discovery boilerplate, labels excerpts as “Dấu hiệu”, and gives the final
three-action bubble stronger visual emphasis.
After Cô tâm lý finishes for a `suspicious` or `dangerous` result, the browser asks which
of four exposure states applies: no action, opened a link, shared information, or sent
money. The first choice locks the group and reveals the frontend-only Người ứng cứu with
an authored, risk-aware numbered action list. Each step is a separate avatar bubble,
revealed at one-second intervals unless reduced motion is enabled. This guidance is not
sent to an API, does not consume quota, and is not persisted.

The browser switches from the composer to a dedicated processing frame while a check is in
progress; it has no browser-cancel control. Online
requests persist a random request ID with the pending message in tab-scoped storage before
calling the API. A manual retry of the same message reuses that ID, so completed work does
not consume quota twice; the browser does not automatically retry or replace an interrupted
online request with an offline result. Completed online results come from session-scoped
database-backed history, while offline results use a separate ten-item `localStorage` history
that is never silently uploaded. The persistent top navigation uses
`#analyze`, `#library`, `#history`, and `#practice` views. Library detail state uses
`#library/{scam_type_id}`. The logo is presentational rather than a navigation link,
and the result header has no extra “check another message” button. A “Trở lại lịch sử”
button appears only while reviewing a saved history result.
History is a dedicated page rather than a dialog; its “Kiểm tra lại” action copies a
message into the analysis composer without calling an API. Online entries render the
replayable response returned by `GET /history/`; offline entries render their bounded local
snapshot. “Xem kết quả” uses the existing full result renderer without regenerating either
entry. Deleting an online entry calls the session-scoped hide route; deleting an offline
entry changes only localStorage.

The service worker caches `/`, `/styles.css`, `/offline-analyzer.js`, `/app.js`,
`/scamcheck-logo.png`, `/detective-avatar.png`, `/psychologist-avatar.png`, and
`/responder-avatar.png` after a successful online visit. When the browser reports that it is
offline, `offline-analyzer.js` performs a conservative rule-based assessment on the device
and labels it as preliminary. It does not call Gemini, consume quota, write the database, or claim
provider accuracy. API responses, submitted text, analysis results, and session usage are
never added to the offline cache. A zero-signal offline result must still warn that it
cannot establish safety.

### Catalog

- The four required scam groups and twelve authored records live in
  `src/data/scam_types.json`; do not duplicate a client-side catalog.
- `src/frontend.py` validates catalog data at import and owns filtering, detail lookup,
  and explicit frontend-asset routes; there is no separate `src/catalog.py`.
- Online link and message assessment belongs to the provider-backed `/analyze` call. The
  browser's offline analyzer is a deliberately limited fallback and must not alter online
  provider results.

### Frontend recognition exercise

- The ten authored prompts, balanced `scam`/`safe` labels, and explanations live only in
  `frontend/app.js`.
- The browser displays one prompt at a time and reveals its label and explanation only
  after the user chooses an answer.
- Grading and score state run in page memory. They do not call an API or Gemini and are
  not stored in localStorage, the server database, or the session cookie.
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

`AnalysisRepository` selects SQLite or PostgreSQL from the database URL. When neither
`DATABASE_URL` nor `SUPABASE_DB_URL` is set, runtime defaults to `sqlite:///app.db`; explicit
SQLite URLs and bare local paths are also accepted. PostgreSQL runtime operations use
short-lived Psycopg connections and disable prepared statements for Supabase transaction-
pooler compatibility. Both backends create and migrate the same logical application tables.
PostgreSQL tables additionally enable Row Level Security without browser-facing policies.

- `analyses` stores raw submitted text, source, validated scores/reasoning, JSON indicator
  data, actions, provider risk level, scenario matrix, and timestamp.
- `ai_calls` stores random call ID, opaque session ID, call kind, input length, pending or
  final success status, summary, and timestamp.
- `analysis_requests` stores a session-scoped random request ID, a content hash, pending or
  completed status, the completed response JSON, and a `history_hidden` flag. It does not
  duplicate raw submitted text. Its response and `analyses` row are committed in one
  transaction; hiding history does not weaken replay idempotency.
- There is intentionally no character-chat endpoint, request schema, conversation table,
  or transcript storage.
- AI-call quota reservation is atomic in both backends: PostgreSQL uses a transaction-scoped
  advisory lock across instances, while SQLite serializes writes for a local app process.
- `_complete_log` intentionally does not fail an otherwise completed API response when an
  audit update fails; it logs the database exception server-side.
- The `scamcheck_session` cookie is HttpOnly, SameSite=Lax, and Secure on HTTPS. It scopes
  audit history only. Analysis IDs are globally retrievable bearer capabilities.

Changing these tables requires backward-compatible migrations for both backends plus a
legacy-schema test in `tests/test_database.py`.

## File implementation map

### Backend

- `src/main.py`: FastAPI composition, lifespan, dependency protocols, cookie middleware,
  global validation handler, AI-call audit orchestration, analysis/history routes, error
  translation, and inclusion of the frontend router. Keep provider logic out of routes and
  persistence-backend details out of this file.
- `src/schemas.py`: public Pydantic request/response models, constrained IDs and text,
  catalog contracts, twelve ordered scam scenario codes, default actions, and model-level
  consistency checks. Provider-only schemas belong in `analyzer.py`, not here.
- `src/analyzer.py`: ordered Gemini/Groq transports, provider response schemas, prompts,
  deadline-aware weighted timeout budgets, strict Groq structured output, redacted failure
  diagnostics, conservative fallback analysis, safe user-facing provider errors, and
  character voice validation. `_generate` tries each
  distinct configured target once and never logs raw submitted text or credentials.
- `src/deterministic_checker.py`: advisory text/domain signals, known-shortener detection,
  explicit opt-in short-link resolution helper, and lookalike/punycode/Cyrillic checks. Its
  output must never impose the authoritative online risk.
- `src/url_extractor.py`: bounded URL extraction and normalization used by deterministic
  checks.
- `src/frontend.py`: validated static catalog filtering/detail routes and the eight
  explicit frontend asset routes.
- `src/data/scam_types.json`: twelve authored scam types; exactly three entries in each of
  the four required groups, with name, description, example message, and group.
- `src/characters.py`: immutable `CharacterSpec` and the `CALMING_GUIDE`/Cô tâm lý voice
  contract used for the optional one-time `/analyze` response.
- `src/database.py`: SQLite/PostgreSQL initialization and migrations, analysis serialization,
  cryptographically random IDs, atomic AI-call reservations, audit completion/history,
  idempotent request claiming/replay, SQLite async thread handoff, and short-lived Supabase
  connections.
- `src/config.py`: `.env` loading, primary/secondary Gemini settings (`GOOGLE_*` preferred
  over legacy `GEMINI_*`), optional Groq settings, local SQLite default and PostgreSQL URL
  aliases (`DATABASE_URL` preferred over `SUPABASE_DB_URL`), stable model defaults, and positive
  `AI_SESSION_CALL_LIMIT` validation. Loading only the database URL does not require
  provider credentials.
- `src/main.py` exports `app` for Vercel; this repository intentionally has no duplicate
  `src/app.py` entrypoint.
- `src/__init__.py`: package marker and short package description.

### Tests and evaluation

- `tests/test_api.py`: ASGI contract tests using `httpx.AsyncClient`, an in-memory
  repository, and `StubAnalyzer`. It covers health, catalog APIs, analyze/get/history
  behavior, the absence of a practice API, session quota/auditing, idempotency, automatic
  character fallback, deterministic advisory propagation, and 409/429/502/503 mapping.
- `tests/test_analyzer.py`: mocked HTTP tests for Gemini/Groq request schemas (including
  Groq strict-mode closure), ordered transport/adaptive-timeout/schema fallbacks, redacted
  failure diagnostics, conservative fallback behavior, character voice enforcement, and
  prompt injection isolation.
- `tests/test_database.py`: repository save/get behavior, SQLite runtime selection,
  PostgreSQL migration SQL coverage, legacy migration, and session-scoped idempotency claims.
- `tests/test_config.py`: database backend selection plus default, override, and invalid
  session-call-limit configuration.
- `tests/test_catalog.py`: catalog size, required fields, and group balance.
- `tests/test_deterministic_checker.py`: text/domain signal, lookalike, punycode, Cyrillic,
  and known-shortener behavior, including proof that the default request path does not
  contact submitted links.
- `tests/test_url_extractor.py`: bounded URL extraction and normalization cases.
- `tests/test_gemini.py` and `tests/mock_gemini.py`: reusable in-process Gemini transport
  integration double.
- `tests/test_live_api.py` and `tests/live_inputs.json`: credential-gated live provider
  checks; never treat them as deterministic offline coverage.
- `tests/test_regression.py`: runs the labeled corpus through the offline HTTP API and
  prints the expected/actual ĐÚNG/SAI table.
- `tests/labeled_messages.json`: 24 deterministic safe, suspicious, and dangerous
  messages, including the four named library groups and prompt-injection attempts.
- `tests/test_frontend.py`: validates that the root page calls the analysis and usage
  APIs online; renders Detective/Cô tâm lý separately; keeps the balanced practice dataset
  and grading in the browser; wires the explicitly preliminary offline analyzer; executes
  representative offline risk/safety cases when Node.js is available; and keeps analysis,
  local history, and practice in separate hash-routed views.
- `tests/factories.py`: canonical ordered scenario builders shared by API/analyzer/database
  tests. Use these instead of hand-building a partial scenario matrix.
- `tests/_logging.py`: disables expected error logs during tests. Import it before code
  paths that intentionally exercise failures.

### Commands, UI, and repository metadata

- `frontend/index.html`: accessible application shell with persistent top navigation,
  separate analysis/library/history/practice views, library list/detail frames, dedicated
  processing and result states, connectivity notice, an icon-only voice control inside the message field,
  Detective result-message markup, and references to the browser assets.
- `frontend/styles.css`: mobile-first page styling, the automatic 900px+ widescreen
  analysis workspace, responsive navigation and result/library/history/practice layouts,
  sequential Detective-then-Cô-tâm-lý message-bubble animations, focus states, and reduced-motion
  behavior.
- `frontend/app.js`: `/analyze` integration, AI-call `used`/`limit` display and limit-state
  handling, safe result rendering, voice input, server-backed online history, bounded
  local-only offline history, the API-backed scam library, local recognition
  prompts/grading/score, and the authored risk/exposure-specific Người ứng cứu action
  lists. It keeps the
  dedicated processing frame during requests, registers the offline shell service worker, routes
  offline submissions through the local analyzer, owns hash-based view switching, and
  supports reusing a history item in the composer. It contains no direct character API
  call, chat UI, or duplicated scam catalog.
- `frontend/offline-analyzer.js`: conservative, browser-only rules that return a compatible
  preliminary risk result without network, quota, cookie, or database access. It is not
  used to override an online provider-chain result.
- `frontend/service-worker.js`: versioned cache for the root page, stylesheet, browser
  scripts, and image assets only. The page, stylesheet, and main script are network-first
  with cached offline fallback so UI fixes are not hidden by stale shell assets. It does
  not intercept or cache API requests or user data.
- `frontend/scamcheck-logo.png`: standalone ScamCheck brand asset.
- `frontend/detective-avatar.png`: Detective avatar shown beside sequential analysis messages.
- `frontend/psychologist-avatar.png`: Cô tâm lý avatar shown in the optional calming-response card.
- `frontend/responder-avatar.png`: transparent Người ứng cứu avatar used in the authored
  post-analysis action bubbles.
- `README.md`: contributor overview and main commands. Keep user-facing setup here; keep
  agent-level invariants in this file.
- `Makefile`: short wrappers for offline API tests, online API tests, and running the app.
- `pyproject.toml`: Python version, runtime dependencies, and package metadata.
- `uv.lock`: reproducible dependency lock; update it through `uv`, never by hand.
- `pyrightconfig.json`: strict checking for `src/` with the local `.venv`.
- `.env.example`: nonsecret provider configuration with optional SQLite/PostgreSQL settings.
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
Detective and character calls each consume one reservation; PostgreSQL rejects reservations
atomically at the ceiling, `/analyze` returns a polite 429 before contacting a provider,
and usage responses contain both `used` and `limit`. The frontend displays the fraction
and disables analysis at the ceiling. Existing per-call timeouts remain 12 seconds for
the Detective and 7.5 seconds for the character.

The recognition exercise was then integrated into the current frontend and moved fully
out of the backend at the user's request. Its ten prompts, labels, explanations, grading,
and page-memory score now live in `frontend/app.js`; the practice routes, public schemas,
catalog helpers, backend sample data, and API tests were removed. The exercise makes no
network, Gemini, PostgreSQL, cookie, or localStorage call. The analysis API, database schema,
and provider prompts did not change.

The offline continuation first added a narrowly scoped service worker, then was clarified
by the user to require actual message analysis without connectivity. The browser now uses
a conservative local rules engine only while offline and clearly labels its output as
preliminary; online analysis remains provider-backed and authoritative. No API response or
submitted text is cached, and offline results do not consume quota or reach PostgreSQL. The
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
Cô tâm lý text, and online/offline mode. The History view reopens this snapshot in the
existing full result screen without an API call, and keeps compatibility with older
message-only entries. Legacy entries clearly show that no saved result is available and can
still be rechecked. No result is regenerated, and the database schema, public response
shapes, provider prompts, and offline rules did not change.

The unstable-connection flow later stopped treating an online request failure as a silent
offline result. It initially stored interrupted analysis state and automatically resumed
after probing `/health`; the 2026-07-19 change above replaced that behavior with an explicit
error and manual retry while preserving only the ordinary composer draft. No API, database,
provider prompt, or public response shape changed.

On 2026-07-20, runtime persistence moved from a process-local SQLite file to Supabase
PostgreSQL so Vercel instances share analyses, AI-call quota records, and idempotent request
claims. Psycopg opens one short-lived connection per repository operation and disables
prepared statements for Supabase transaction-pooler compatibility. PostgreSQL advisory
locks serialize schema setup and per-session quota reservations across instances; JSON
payloads use JSONB, timestamps use `TIMESTAMPTZ`, and all three application tables enable
Row Level Security without browser-facing policies. `src/app.py` was added only as Vercel's
recognized FastAPI entrypoint. The public API, frontend, provider prompts, and offline
analysis behavior did not change. The SQLite `:memory:` path remains test-only so the
deterministic suite does not require cloud credentials; no file-backed SQLite runtime is
accepted.

Later on 2026-07-20, online generation gained an actual ordered fallback chain: primary
Gemini, stable Gemini Flash-Lite, then Groq GPT-OSS when `GROQ_API_KEY` is present. Each
target receives a bounded share of the existing total timeout, and transport or structured
validation failures advance without sleeping or repeatedly calling the same unavailable
model. The conservative suspicious result remains the final response only when providers
respond but every response is malformed. Unused Flask, Google SDK, and Argon2 dependencies
were removed because all provider transport already uses `httpx` and no authentication
password hashing exists. The UI now labels saved online results generically rather than as
Gemini-only, and the service-worker shell version was bumped. The API response shape,
database schema, quota semantics, offline rules, and provider prompts did not change.

The provider chain was then hardened after live failures exposed three independent causes.
Groq GPT-OSS now receives a recursively closed strict JSON Schema and at least 1,024
completion tokens, reducing incomplete or structurally invalid responses. Each attempt gets
a weighted share of the current remaining deadline, so fast failures donate their unused
time to later targets while the overall call remains bounded. Provider failure logs now
record only target identity, elapsed and allocated seconds, and a safe HTTP/timeout/schema
summary. The optional Cô tâm lý deadline increased to 7.5 seconds while keeping the worst
sequential Detective-plus-character budget below 20 seconds. Its user prompt now repeats
the configured required and forbidden voice terms because live Groq output could satisfy the
schema while omitting `cô` or `bác`; server-side voice validation remains authoritative. The
frontend, database schema, public response shape, quota semantics, offline rules, and
Detective prompt did not change.

The later merge of the Detective presentation added a separately served avatar, sequential
result-message bubbles, risk-aware evidence highlighting, and suppression of the Cô tâm lý
panel for safe results. Core UI shell files now refresh network-first while retaining cached
offline fallback. Its proposed request-time scan screen and forced 1.4-second delay were not
retained: the composer remains visible and only its controls are disabled during analysis.
Friendly Vietnamese 502 details were integrated with the provider chain without restoring
same-model retry sleeps. The database schema, public response shape, offline rules, and
provider prompts did not change.

On 2026-07-21, the coherent provider/database implementation from `old-backup` was combined
with the rewrite's useful modules rather than replacing either side wholesale. The current
application preserves `deterministic_checker.py`, `url_extractor.py`, lookalike/punycode/
Cyrillic detection, known-shortener handling, `tests/live_inputs.json`, the reusable mocked
Gemini server, and `frontend.py` router organization. Deterministic results are advisory and
run alongside provider analysis without contacting submitted URLs in the normal path. Online
history now comes from cached, session-scoped PostgreSQL idempotency responses; offline
history remains bounded in localStorage and is never silently uploaded. Automatic Cô tâm lý
generation is part of the single idempotent `/analyze` response, so there is no `/guide/`
endpoint. Vercel imports `src/main.py` directly, so the obsolete duplicate `src/app.py` is
not present. The combined offline suite covers both the restored provider/database contracts
and the rewrite's deterministic/URL modules.

On 2026-07-23, the result sequence gained a frontend-only post-analysis triage step. After
Cô tâm lý finishes for suspicious or dangerous results, the user may select exactly one
of four exposure states. That choice reveals the third character, Người ứng cứu, whose
authored guidance varies by exposure and risk level and contains only a numbered list of
actions. No provider call, API schema, database field, audit record, or chat endpoint was
added. The Người ứng cứu steps use a dedicated transparent avatar and appear as
one-second sequential bubbles matching the Cô tâm lý conversation pattern.

Later on 2026-07-23, all three character sequences moved to one-second progressive DOM
reveal rather than block-level delayed animation. Detective evidence copy was shortened,
the final three-action card was visually strengthened, and Cô tâm lý emoji became
sentence-aware. The API response, provider prompts, persistence, quota, and offline
analysis contracts did not change.

Later on 2026-07-21, file-backed SQLite runtime support was restored for local development.
With no database environment variable, configuration now selects `sqlite:///app.db`;
explicit SQLite URLs, bare local paths, and the existing PostgreSQL/Supabase URLs remain
supported. PostgreSQL is still the recommended backend for shared or multi-instance
deployments. The API, frontend, logical database schema, provider prompts, quota semantics,
and offline analysis rules did not change.

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
