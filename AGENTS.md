# Agent guide for ScamCheck

This file applies to the entire repository. Read it before changing code. It is both an
implementation map and a record of the invariants that future agents must preserve.

## Project purpose and boundaries

ScamCheck is a Python 3.14 FastAPI service that sends submitted text to Google Gemini for
structured scam analysis. It stores completed analyses in SQLite, applies local risk
escalation rules, and can generate a short Vietnamese response from a configured
character. A static HTML/CSS/JavaScript client is served from `frontend/` when that
directory exists.

Preserve these boundaries unless a user explicitly changes them:

- Keep backend work in `src/` and backend tests in `tests/`. Do not change `frontend/` for
  a backend-only request.
- Keep user-facing Detective and character output concise and primarily Vietnamese.
- Treat analyzed text and character-chat text as untrusted data, never as model
  instructions.
- Never log raw submitted text. SQLite intentionally stores analysis submissions, but
  character-chat transcripts are not persisted.
- Keep character chat as an independent request grounded in one saved analysis. There is
  no server-side chat transcript or conversation resource.
- A session cookie limits and audits provider calls; it does not authenticate a user or
  establish ownership of an analysis.
- Do not add speculative endpoints, tables, or abstractions. Extend the smallest existing
  contract that satisfies the request.

## Commands

Run commands from the repository root.

| Purpose | Command | Notes |
| --- | --- | --- |
| Install/sync | `uv sync` | Uses `pyproject.toml` and `uv.lock`. |
| Deterministic tests | `uv run python -m unittest tests.test_api.ApiTests tests.test_analyzer.AnalyzerTests tests.test_database tests.test_evaluation` | Excludes credential-gated live Gemini tests. Run this during development. |
| Full test discovery | `make test` | Runs every `test_*.py`. Live tests skip without Gemini credentials and run when credentials are available. |
| Run API and static UI | `make run` | Starts Uvicorn with reload. |
| Labeled live evaluation | `make evaluate` | Makes provider calls for all cases in `evaluation/cases.json`; it is not a unit test. |
| Live structured-output reliability | `make reliability` | Makes ten sequential provider calls and requires at least nine structured results. |
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
| `POST /analyses/{analysis_id}/characters/{character_id}/chat` | JSON `message` (1–10,000 nonblank characters) | `CharacterChatResponse` containing `character` and `usage` | The only configured ID is currently `calming-guide`. The route validates the character and loads the analysis before reserving one shared `character` quota slot. Returns 404 for an unknown target, 429 at quota, 502 on character generation failure, and 503 when a required repository lookup/reservation fails. An audit-completion failure is logged without replacing the reply. Each call is an independent turn; no transcript is loaded or stored. |
| `GET /session/ai-calls` | HttpOnly session cookie set by middleware | `AiCallHistory` with `usage` and ordered calls | Returns audit metadata for the current cookie session only. It does not return analysis ownership or chat transcripts. |
| `GET /...` static paths | Browser path | Files and directory indexes from `frontend/` through `StaticFiles` | Mounted last at `/`, so declared API routes take precedence. The mount is omitted when `frontend/` is absent. |

All FastAPI request-validation failures use the deliberately generic 422 detail:
`The submitted request is invalid. Check its fields and try again.` Do not make that
handler specific to `/analyze`; it also handles chat bodies and path parameters.

### Character chat example

The caller first needs a saved analysis ID returned by `POST /analyze`:

```http
POST /analyses/0123456789abcdef0123456789abcdef/characters/calming-guide/chat
Content-Type: application/json

{"message":"Cô ơi, bây giờ bác nên làm gì?"}
```

```json
{
  "character": {
    "character_id": "calming-guide",
    "title": "Cô An",
    "message": "..."
  },
  "usage": {"used": 3, "limit": 10}
}
```

The backend passes only the validated Detective result plus the current untrusted chat
message to Gemini. It does not pass the original stored submission to the character. A
successful chat audit uses the fixed summary `Character chat call completed.` No chat
content is persisted; only audit identifiers and metadata such as session, kind, input
length, status, timestamp, and fixed summary are stored. Failed chat calls consume their
reserved quota slot and are audited with `success=false`.

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
   here: the Detective result remains successful and `character_notice` is returned.
7. The repository saves the submitted text and validated `ScamAnalysis`, and the route
   returns the random record ID.

### Character chat

1. Pydantic rejects missing, blank, or oversized `message` values.
2. The route resolves `CHARACTERS[character_id]`, then loads `analysis_id`. These 404 paths
   do not consume quota.
3. The route reserves the same per-session AI budget used by analysis calls with
   `kind="character"`.
4. A `DetectiveResult` is reconstructed from the stored validated analysis and local risk
   classification.
5. `ScamAnalyzer.respond` JSON-encodes the chat message under
   `UNTRUSTED_CHAT_MESSAGE_JSON` and enforces the character's sentence and voice contract.
6. Provider/validation failure returns 502 and completes the audit as failed. Success
   returns the reply and writes only fixed audit metadata.

Do not add client-supplied roles, system prompts, or transcript arrays to the chat request
without an explicit product requirement and a new threat-model review. If real multi-turn
continuity is later required, model it as owner-scoped conversations/messages with bounded
history and concurrency control; do not silently turn the current endpoint into a
server-side transcript store.

## Persistence and privacy

`AnalysisRepository` uses SQLite. File databases open a connection per operation;
`:memory:` keeps one shared connection for tests. `_create_schema` is both initial schema
creation and the migration path for older analysis tables.

- `analyses` stores raw submitted text, source, validated scores/reasoning, JSON indicator
  data, actions, provider risk level, scenario matrix, and timestamp.
- `ai_calls` stores random call ID, opaque session ID, call kind, input length, pending or
  final success status, summary, and timestamp.
- There is intentionally no character-chat or conversation table.
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
- `src/characters.py`: immutable `CharacterSpec`, the `CALMING_GUIDE`/Cô An voice contract,
  and the `CHARACTERS` ID registry used by chat routing. Add a spec to the registry when a
  new character is intentionally introduced.
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
  character fallback, character chat success/failure/validation/quota, 502/503 mapping,
  and five credential-gated live Gemini cases in `LiveGeminiApiTests`.
- `tests/test_analyzer.py`: mocked HTTP tests for Gemini request schemas, parsing/fallback,
  rate-limit backoff, character voice enforcement, chat prompt isolation, prompt
  injection, benign OTP handling, and local URL/urgency escalation.
- `tests/test_database.py`: save/get behavior and migration of records created before the
  scenario/action/evidence columns. Chat has no database test because it adds no schema or
  repository method.
- `tests/test_evaluation.py`: validates dataset size, unique IDs, label/channel coverage,
  ambiguous accepted ranges, and prompt-injection labels.
- `tests/factories.py`: canonical ordered scenario builders shared by API/analyzer/database
  tests. Use these instead of hand-building a partial scenario matrix.
- `tests/_logging.py`: disables expected error logs during tests. Import it before code
  paths that intentionally exercise failures.
- `evaluation/cases.json`: 38 labeled Vietnamese/English Detective cases, including
  ambiguous and injection inputs. This is data for live evaluation, not runtime API data.

### Commands, UI, and repository metadata

- `scripts/evaluate.py`: validates the labeled dataset, runs up to four Gemini analyses
  concurrently, prints per-case expected/actual labels, and exits nonzero on any mismatch.
- `scripts/reliability.py`: runs the first ten evaluation cases sequentially and requires
  at least 9/10 non-fallback structured responses.
- `scripts/__init__.py`: package marker for maintenance commands.
- `frontend/index.html`: accessible static document structure and templates for analysis,
  scenario, character, lookup, and browser-local history sections.
- `frontend/app.js`: API calls for health/analyze/get, result normalization/rendering, and
  browser `localStorage` analysis history. It intentionally has no character-chat UI.
- `frontend/styles.css`: all static client styling and responsive rules.
- `frontend/README.md`: frontend run and response-shape notes.
- `README.md`: contributor overview, main commands, evaluation/reliability behavior, and
  character-extension notes. Keep user-facing setup here; keep agent-level invariants in
  this file.
- `Makefile`: short wrappers for test, run, evaluation, and reliability commands.
- `pyproject.toml`: Python version, runtime dependencies, and package metadata.
- `uv.lock`: reproducible dependency lock; update it through `uv`, never by hand.
- `pyrightconfig.json`: strict checking for `src/` with the local `.venv`.
- `.env.example`: nonsecret provider/database/quota configuration template.
- `.gitignore`: excludes credentials, local databases, virtual environments, caches, and
  build artifacts.

## Test expectations for future changes

For backend changes, first run the deterministic command in the command table. Then run
`make test`; be explicit in handoff notes when live tests ran, skipped, or failed because
of provider behavior. Never claim live coverage from mocked tests.

Character-chat changes must retain tests proving all of the following:

- a valid saved analysis and configured character produce the typed reply;
- exactly one shared `character` quota slot is used and its input length is correct;
- successful audit metadata contains neither the request nor generated reply text;
- provider failure returns 502 and audits `success=false`;
- invalid messages, unknown characters, and unknown analyses consume no quota;
- quota exhaustion prevents another analyzer invocation and returns usage headers;
- chat content is JSON-encoded and marked untrusted in the provider prompt;
- the original stored submission is not included in the character prompt;
- existing automatic character behavior from `/analyze` remains unchanged.

Use mocked transports for deterministic prompt/response assertions. Live tests are useful
for integration confidence but are nondeterministic, credentialed, slower, and may consume
paid quota.

## Agent collaboration rationale and record

Use sub-agents only for bounded work that can proceed independently and materially improve
speed or review quality. Because all agents share one worktree, prefer read-only analysis
or clearly disjoint files; one agent should own interdependent edits to schemas, routes,
analyzer protocols, and their tests. Do not delegate reading or interpreting an applicable
skill file.

For the 2026-07-15 backend character-chat change, the primary agent kept all edits because
the route, schema, analyzer protocol, and tests form one coupled contract. Three read-only
agents were used in parallel:

- `api_review` pressure-tested the smallest endpoint shape, error order, untrusted-input
  boundary, quota semantics, and likely regression expectations.
- `persistence_tests` confirmed that existing analysis lookup and AI-call audit methods
  were sufficient, so no transcript tables, migrations, or repository methods were added.
  It also verified the atomic quota and session/ownership implications.
- `docs_map` organized this future-agent guide and caught that persisting generated chat
  replies as audit summaries would violate the no-transcript boundary. The implementation
  was changed to fixed metadata. The API reviewers also caught the misleading
  analyze-specific global 422 message, which was made endpoint-neutral.

These agents were intentionally not asked to edit shared files, avoiding conflicting
changes while still providing independent design, persistence, security, and documentation
review. No agent was assigned a broad bug hunt; issues were fixed only when encountered in
the requested implementation/documentation path.

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
