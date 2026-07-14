"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
import logging
from contextlib import asynccontextmanager
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.staticfiles import StaticFiles

from .analyzer import AnalysisError, ScamAnalyzer
from .config import Settings, load_database_path, load_settings
from .database import AnalysisRepository, DatabaseError
from .schemas import AnalyzeRequest, AnalyzeResponse, StoredAnalysis

logger = logging.getLogger(__name__)


async def get_analyzer(request: Request) -> ScamAnalyzer:
    return request.app.state.analyzer


async def get_repository(request: Request) -> AnalysisRepository:
    return request.app.state.repository


def create_app(
    settings: Settings | None = None,
    analyzer: ScamAnalyzer | None = None,
    repository: AnalysisRepository | None = None,
) -> FastAPI:
    repository_instance = repository or AnalysisRepository(
        settings.database_path if settings is not None else load_database_path()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configured_settings = settings or load_settings()
        app.state.analyzer = analyzer or ScamAnalyzer(configured_settings)
        await repository_instance.initialize()
        logger.info("Scam analysis API started with model %s", configured_settings.google_model)
        try:
            yield
        finally:
            close = getattr(app.state.analyzer, "aclose", None)
            if close is not None:
                await close()
            repository_instance.close()

    app = FastAPI(title="Scam Analysis API", version="0.1.0", lifespan=lifespan)
    # Setting injected services here also supports ASGI test clients without lifespan handling.
    app.state.analyzer = analyzer
    app.state.repository = repository_instance

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/analyze", response_model=AnalyzeResponse)
    async def analyze(
        payload: AnalyzeRequest,
        analyzer: ScamAnalyzer = Depends(get_analyzer),
        repository: AnalysisRepository = Depends(get_repository),
    ) -> AnalyzeResponse:
        try:
            analysis = await analyzer.analyze(payload)
        except AnalysisError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to complete scam analysis at this time",
            ) from exc

        try:
            record_id = await repository.save(payload, analysis)
        except DatabaseError as exc:
            logger.exception("Failed to persist completed scam analysis")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to save scam analysis at this time",
            ) from exc

        return AnalyzeResponse(id=record_id, **analysis.model_dump())

    @app.get("/analyses/{analysis_id}", response_model=StoredAnalysis)
    async def get_analysis(
        analysis_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
        repository: AnalysisRepository = Depends(get_repository),
    ) -> StoredAnalysis:
        try:
            analysis = await repository.get(analysis_id)
        except DatabaseError as exc:
            logger.exception("Failed to retrieve stored scam analysis")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve scam analysis at this time",
            ) from exc

        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scam analysis not found",
            )
        return analysis

    frontend_directory = FilePath(__file__).resolve().parent.parent / "frontend"
    if frontend_directory.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=frontend_directory, html=True),
            name="frontend",
        )

    return app


app = create_app()
