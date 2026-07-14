"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status

from .analyzer import AnalysisError, ScamAnalyzer
from .config import Settings, load_settings
from .schemas import AnalyzeRequest, ScamAnalysis

logger = logging.getLogger(__name__)


async def get_analyzer(request: Request) -> ScamAnalyzer:
    return request.app.state.analyzer


def create_app(settings: Settings | None = None, analyzer: ScamAnalyzer | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configured_settings = settings or load_settings()
        app.state.analyzer = analyzer or ScamAnalyzer(configured_settings)
        logger.info("Scam analysis API started with model %s", configured_settings.google_model)
        try:
            yield
        finally:
            close = getattr(app.state.analyzer, "aclose", None)
            if close is not None:
                await close()

    app = FastAPI(title="Scam Analysis API", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/analyze", response_model=ScamAnalysis)
    async def analyze(
        payload: AnalyzeRequest,
        analyzer: ScamAnalyzer = Depends(get_analyzer),
    ) -> ScamAnalysis:
        try:
            return await analyzer.analyze(payload)
        except AnalysisError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to complete scam analysis at this time",
            ) from exc

    return app


app = create_app()
