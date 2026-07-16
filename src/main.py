from collections.abc import AsyncGenerator, Awaitable, Callable
import logging
from contextlib import asynccontextmanager
from pathlib import Path as FilePath
from secrets import token_hex
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import AnalysisError, CharacterError, ScamAnalyzer, classify_risk
from .characters import CALMING_GUIDE, CharacterSpec
from .config import DEFAULT_AI_SESSION_CALL_LIMIT, Settings, load_database_path, load_settings
from .database import AiCallReservation, AnalysisRepository, DatabaseError
from .schemas import (
    AiCallHistory,
    AiCallLog,
    AiCallUsage,
    AnalyzeRequest,
    AnalyzeResponse,
    CharacterReply,
    DetectiveResult,
    ScamAnalysis,
    StoredAnalysis,
)

logger = logging.getLogger(__name__)
router = APIRouter()
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
    if active_analyzer is None:
        configured_settings = configured_settings or load_settings()
        active_analyzer = ScamAnalyzer(configured_settings)
        app.state.analyzer = active_analyzer

    repository = cast(Repository, app.state.repository)
    await repository.initialize()
    if configured_settings is not None:
        logger.info("Scam analysis API started with model %s", configured_settings.google_model)
    try:
        yield
    finally:
        await active_analyzer.aclose()
        repository.close()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    request: Request,
    analyzer: Analyzer = Depends(get_analyzer),
    repository: Repository = Depends(get_repository),
) -> AnalyzeResponse:
    session_id = _session_id(request)
    call_limit = cast(int, request.app.state.ai_session_call_limit)
    reservation = await _use_database(
        repository.reserve_ai_call(session_id, "detective", len(payload.text), call_limit),
        "reserve",
    )
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "This session has reached its AI call limit. Please review saved results "
                "instead of submitting another request."
            ),
            headers={
                "X-AI-Calls-Used": str(call_limit),
                "X-AI-Calls-Limit": str(call_limit),
            },
        )
    try:
        analysis = await analyzer.analyze(payload)
    except AnalysisError as exc:
        await _complete_log(repository, reservation.call_id, False, "Detective call failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete scam analysis at this time",
        ) from exc

    detective = DetectiveResult(
        **analysis.model_dump(),
        risk_level=classify_risk(payload.text, analysis),
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
                "Phiên này đã dùng hết lượt AI; bác xem kết luận của Thám tử trước nhé."
            )
        else:
            usage = character_reservation.usage
            try:
                character_reply = await analyzer.respond(CALMING_GUIDE, detective)
            except CharacterError:
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

    record_id = await _use_database(repository.save(payload, analysis), "save")
    return AnalyzeResponse(
        id=record_id,
        detective=detective,
        character=character_reply,
        character_notice=character_notice,
        usage=usage,
    )


@router.get("/session/ai-calls", response_model=AiCallHistory)
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


@router.get("/analyses/{analysis_id}", response_model=StoredAnalysis)
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


def create_app(
    settings: Settings | None = None,
    analyzer: Analyzer | None = None,
    repository: Repository | None = None,
) -> FastAPI:
    repository_instance: Repository = repository or AnalysisRepository(
        settings.database_path if settings is not None else load_database_path()
    )
    app = FastAPI(title="Scam Analysis API", version="0.1.0", lifespan=lifespan)
    # Setting injected services here also supports ASGI test clients without lifespan handling.
    app.state.settings = settings
    app.state.analyzer = analyzer
    app.state.repository = repository_instance
    app.state.ai_session_call_limit = (
        settings.ai_session_call_limit if settings else DEFAULT_AI_SESSION_CALL_LIMIT
    )
    app.middleware("http")(session_cookie_middleware)
    app.exception_handler(RequestValidationError)(validation_error_handler)
    app.include_router(router)

    frontend_directory = FilePath(__file__).resolve().parent.parent / "frontend"
    if frontend_directory.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=frontend_directory, html=True),
            name="frontend",
        )

    return app


app = create_app()
