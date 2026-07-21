import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from hashlib import sha256
import logging
from secrets import token_hex
from typing import Annotated, Protocol, cast

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Request,
    Response,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .analyzer import AnalysisError, CharacterError, ScamAnalyzer
from .characters import CALMING_GUIDE, CharacterSpec
from .config import (
    DEFAULT_AI_SESSION_CALL_LIMIT,
    Settings,
    load_database_url,
    load_settings,
)
from .database import (
    AiCallReservation,
    AnalysisRepository,
    AnalysisRequestClaim,
    DatabaseError,
)
from .deterministic_checker import check_message
from .frontend import router as frontend_router
from .schemas import (
    AiCallHistory,
    AiCallLog,
    AiCallUsage,
    AnalyzeRequest,
    AnalyzeResponse,
    CharacterReply,
    DeterministicFinding,
    DetectiveResult,
    HistoryEntry,
    ScamAnalysis,
    StoredAnalysis,
)

logger = logging.getLogger(__name__)
SESSION_COOKIE = "scamcheck_session"


class Analyzer(Protocol):
    async def analyze(self, request: AnalyzeRequest) -> ScamAnalysis: ...

    async def respond(
        self,
        character: CharacterSpec,
        detective: DetectiveResult,
    ) -> CharacterReply: ...

    async def aclose(self) -> None: ...


class Repository(Protocol):
    async def initialize(self) -> None: ...

    async def save(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str: ...

    async def claim_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> AnalysisRequestClaim: ...

    async def save_idempotent(
        self,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
        session_id: str,
        request_id: str,
        request_hash: str,
        response: AnalyzeResponse,
    ) -> None: ...

    async def release_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> None: ...

    async def get(self, record_id: str) -> StoredAnalysis | None: ...

    async def reserve_ai_call(
        self, session_id: str, kind: str, input_length: int, limit: int
    ) -> AiCallReservation | None: ...

    async def complete_ai_call(
        self, call_id: str, success: bool, summary: str
    ) -> None: ...

    async def get_ai_calls(
        self, session_id: str, limit: int
    ) -> tuple[AiCallUsage, list[AiCallLog]]: ...

    async def get_history(self, session_id: str) -> list[HistoryEntry]: ...

    async def hide_history(self, session_id: str, record_id: str) -> bool: ...

    def close(self) -> None: ...


async def get_analyzer(request: Request) -> Analyzer:
    return cast(Analyzer, request.app.state.analyzer)


async def get_repository(request: Request) -> Repository:
    return cast(Repository, request.app.state.repository)


async def _use_database[T](operation: Awaitable[T], action: str) -> T:
    try:
        return await operation
    except DatabaseError as exc:
        logger.exception("Failed to %s scam analysis", action)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to {action} scam analysis at this time",
        ) from exc


def _valid_session_id(value: str | None) -> bool:
    return value is not None and len(value) == 32 and all(
        character in "0123456789abcdef" for character in value
    )


async def session_cookie_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    is_new = not _valid_session_id(session_id)
    if is_new:
        session_id = token_hex(16)
    request.state.session_id = session_id
    response = await call_next(request)
    if is_new:
        response.set_cookie(
            SESSION_COOKIE,
            cast(str, session_id),
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
    return response


def _session_id(request: Request) -> str:
    return cast(str, request.state.session_id)


async def _complete_log(
    repository: Repository, call_id: str, success: bool, summary: str
) -> None:
    try:
        await repository.complete_ai_call(call_id, success, summary)
    except DatabaseError:
        logger.exception("Unable to complete AI call audit log %s", call_id)


async def _release_analysis_request(
    repository: Repository,
    session_id: str,
    request_id: str | None,
    request_hash: str | None,
) -> None:
    if request_id is None or request_hash is None:
        return
    try:
        await repository.release_analysis_request(session_id, request_id, request_hash)
    except DatabaseError:
        logger.exception("Unable to release analysis request %s", request_id)


async def validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "The submitted request is invalid. Check its fields and try again."
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configured_settings = cast(Settings | None, app.state.settings)
    active_analyzer = cast(Analyzer | None, app.state.analyzer)
    repository = cast(Repository | None, app.state.repository)
    if active_analyzer is None:
        configured_settings = configured_settings or load_settings()
        active_analyzer = ScamAnalyzer(configured_settings)
        app.state.analyzer = active_analyzer
    if repository is None:
        database_url = (
            configured_settings.database_url
            if configured_settings is not None and configured_settings.database_url
            else load_database_url()
        )
        repository = AnalysisRepository(database_url)
        app.state.repository = repository

    await repository.initialize()
    if configured_settings is not None:
        logger.info("Scam analysis API started with model %s", configured_settings.google_model)
    try:
        yield
    finally:
        await active_analyzer.aclose()
        repository.close()


@frontend_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@frontend_router.post("/analyze/", response_model=AnalyzeResponse, include_in_schema=False)
@frontend_router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    request: Request,
    request_id: Annotated[
        str | None,
        Header(
            alias="X-ScamCheck-Request-ID",
            min_length=16,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ] = None,
    analyzer: Analyzer = Depends(get_analyzer),
    repository: Repository = Depends(get_repository),
) -> AnalyzeResponse:
    session_id = _session_id(request)
    effective_request_id = request_id or token_hex(16)
    request_hash = sha256(payload.model_dump_json().encode("utf-8")).hexdigest()
    claim = await _use_database(
        repository.claim_analysis_request(
            session_id, effective_request_id, request_hash
        ),
        "claim",
    )
    if claim.status == "completed" and claim.response is not None:
        return claim.response
    if claim.status == "conflict":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request ID was already used for different content.",
            headers={"X-ScamCheck-Request-Status": "conflict"},
        )
    if claim.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This analysis is still processing.",
            headers={
                "Retry-After": "2",
                "X-ScamCheck-Request-Status": "pending",
            },
        )

    call_limit = cast(int, request.app.state.ai_session_call_limit)
    reservation = await _use_database(
        repository.reserve_ai_call(
            session_id, "detective", len(payload.text), call_limit
        ),
        "reserve",
    )
    if reservation is None:
        await _release_analysis_request(
            repository, session_id, effective_request_id, request_hash
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Phiên này đã dùng hết lượt kiểm tra AI. Bác vui lòng xem lại "
                "các kết quả đã lưu thay vì gửi thêm yêu cầu."
            ),
            headers={
                "X-AI-Calls-Used": str(call_limit),
                "X-AI-Calls-Limit": str(call_limit),
            },
        )
    deterministic_task = asyncio.create_task(check_message(payload.text))
    try:
        analysis = await analyzer.analyze(payload)
    except AnalysisError as exc:
        deterministic_task.cancel()
        with suppress(asyncio.CancelledError):
            await deterministic_task
        await _complete_log(
            repository, reservation.call_id, False, "Detective call failed."
        )
        await _release_analysis_request(
            repository, session_id, effective_request_id, request_hash
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.user_message,
        ) from exc

    try:
        deterministic_result = await deterministic_task
        deterministic_findings = [
            DeterministicFinding(
                kind=item.kind,
                severity=item.severity,
                excerpt=item.excerpt[:500],
                details=item.details[:500] if item.details else None,
            )
            for item in deterministic_result.findings[:10]
        ]
    except Exception as exc:
        logger.warning(
            "Deterministic supporting checks unavailable: %s",
            type(exc).__name__,
        )
        deterministic_findings = []

    detective = DetectiveResult(
        **analysis.model_dump(),
        risk_level=analysis.provider_risk_level or "suspicious",
    )
    await _complete_log(
        repository,
        reservation.call_id,
        True,
        f"{detective.risk_level}: {detective.reasoning}"[:500],
    )
    usage = reservation.usage
    character_reply: CharacterReply | None = None
    character_notice: str | None = None
    if detective.risk_level in CALMING_GUIDE.trigger_levels:
        character_reservation = await _use_database(
            repository.reserve_ai_call(
                session_id, "character", len(payload.text), call_limit
            ),
            "reserve",
        )
        if character_reservation is None:
            character_notice = (
                "Phiên này đã dùng hết lượt AI; bác xem kết luận của Thám tử "
                "trước nhé."
            )
        else:
            usage = character_reservation.usage
            try:
                character_reply = await analyzer.respond(CALMING_GUIDE, detective)
            except (CharacterError, ValueError):
                await _complete_log(
                    repository,
                    character_reservation.call_id,
                    False,
                    "Optional character call failed.",
                )
                character_notice = (
                    "Cô tâm lý đang bận một chút, bác xem kết luận của Thám tử trước nhé."
                )
            else:
                await _complete_log(
                    repository,
                    character_reservation.call_id,
                    True,
                    character_reply.message,
                )

    response = AnalyzeResponse(
        id=token_hex(16),
        detective=detective,
        character=character_reply,
        character_notice=character_notice,
        deterministic_findings=deterministic_findings,
        usage=usage,
    )
    try:
        await _use_database(
            repository.save_idempotent(
                payload,
                analysis,
                session_id,
                effective_request_id,
                request_hash,
                response,
            ),
            "save",
        )
    except HTTPException:
        await _release_analysis_request(
            repository, session_id, effective_request_id, request_hash
        )
        raise
    return response


@frontend_router.get("/session/ai-calls", response_model=AiCallHistory)
async def get_ai_call_history(
    request: Request,
    repository: Repository = Depends(get_repository),
) -> AiCallHistory:
    session_id = _session_id(request)
    call_limit = cast(int, request.app.state.ai_session_call_limit)
    usage, calls = await _use_database(
        repository.get_ai_calls(session_id, call_limit), "retrieve"
    )
    return AiCallHistory(usage=usage, calls=calls)


@frontend_router.get("/analyses/{analysis_id}", response_model=StoredAnalysis)
async def get_analysis(
    analysis_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
    repository: Repository = Depends(get_repository),
) -> StoredAnalysis:
    analysis = await _use_database(repository.get(analysis_id), "retrieve")
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scam analysis not found",
        )
    return analysis


@frontend_router.get("/history/", response_model=list[HistoryEntry])
@frontend_router.get("/history", response_model=list[HistoryEntry], include_in_schema=False)
async def get_history(
    request: Request,
    repository: Repository = Depends(get_repository),
) -> list[HistoryEntry]:
    return await _use_database(
        repository.get_history(_session_id(request)), "retrieve"
    )


@frontend_router.delete("/history/{analysis_id}", status_code=204)
async def delete_history(
    analysis_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
    request: Request,
    repository: Repository = Depends(get_repository),
) -> None:
    hidden = await _use_database(
        repository.hide_history(_session_id(request), analysis_id), "update"
    )
    if not hidden:
        raise HTTPException(status_code=404, detail="History item not found")


def create_app(
    settings: Settings | None = None,
    analyzer: Analyzer | None = None,
    repository: Repository | None = None,
) -> FastAPI:
    app = FastAPI(title="Scam Analysis API", version="0.1.0", lifespan=lifespan)
    # Setting injected services here also supports ASGI test clients without lifespan handling.
    app.state.settings = settings
    app.state.analyzer = analyzer
    app.state.repository = repository
    app.state.ai_session_call_limit = (
        settings.ai_session_call_limit
        if settings is not None
        else DEFAULT_AI_SESSION_CALL_LIMIT
    )
    app.middleware("http")(session_cookie_middleware)
    app.exception_handler(RequestValidationError)(validation_error_handler)
    app.include_router(frontend_router)

    return app


app = create_app()
