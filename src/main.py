from typing import Annotated
from uuid import UUID, uuid4
from contextlib import asynccontextmanager
import logging

from fastapi import Body, Cookie, Depends, FastAPI, HTTPException, Response
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from .database import HistoryDatabase, HistoryEntry
from .deterministic_checker import check_message
from .frontend import router as frontend_router
from .schema import (
    DETECTIVE,
    GUIDE,
    Analysis,
    GuideOutput,
    Settings,
)
from .wrapper import GeminiWrapper

logger = logging.getLogger(__name__)

if not load_dotenv(override=True):
    print("Could not load .env file")
    raise SystemExit

settings = Settings.from_environment()
database = HistoryDatabase(":memory:")
client = GeminiWrapper.from_settings(settings)
session_call_counts: dict[str, int] = {}


def get_client() -> GeminiWrapper:
    return client


ClientDep = Annotated[GeminiWrapper, Depends(get_client)]


def consume_ai_call(response: Response, session_id: str | None) -> str:
    if session_id is None:
        session_id = str(uuid4())
        response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    calls = session_call_counts.get(session_id, 0)
    if calls >= settings.ai_session_call_limit:
        raise HTTPException(429, "AI session call limit reached")
    session_call_counts[session_id] = calls + 1
    return session_id


@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.connect()
    try:
        yield
    finally:
        await database.close()
        await client.close()


app = FastAPI(lifespan=lifespan)
app.include_router(frontend_router)


@app.post("/analyze/")
async def analyze(
    client: ClientDep,
    response: Response,
    data: Annotated[str, Body(...)],
    session_id: Annotated[str | None, Cookie()] = None,
) -> Analysis:
    session_id = consume_ai_call(response, session_id)
    deterministic_result = await check_message(data)

    try:
        detective_analysis = await client.generate(DETECTIVE, data)
    except Exception as e:
        logger.exception(f"Gemini analysis generation failed with exception {e}")
        response.status_code = 502
        return Analysis(success=False)

    result = Analysis(
        success=True,
        analysis=detective_analysis,
        deterministic_findings=deterministic_result.findings,
        deterministic_risk_floor=deterministic_result.risk_floor,
    )
    await database.save_analysis(session_id, data, result)
    return result


@app.post(
    "/guide/",
    response_model=GuideOutput,
    responses={204: {"description": "Guide unavailable for low-risk analysis"}},
)
async def guide(
    client: ClientDep,
    history_id: Annotated[UUID, Body(...)],
) -> GuideOutput | Response:
    item = await database.get_history_item(str(history_id))
    if item is None:
        raise HTTPException(404, "History item not found")

    stored_analysis = Analysis.model_validate(item["analysis"])
    analysis = stored_analysis.analysis

    if analysis is None:
        raise HTTPException(409, "Successful analysis is required")
    if stored_analysis.risk_level == "low":
        return Response(status_code=204)
    if item["guide_output"] is not None:
        return GuideOutput(data=item["guide_output"])

    try:
        output = await client.generate(GUIDE, analysis.model_dump_json())
    except Exception as e:
        logger.exception(f"Gemini guide generation failed with exception {e}")
        raise HTTPException(502, "AI guide generation failed") from e

    await database.save_guide_output(str(history_id), output.data)
    return output


@app.get("/history/")
async def history(
    session_id: Annotated[str | None, Cookie()] = None,
) -> list[HistoryEntry]:
    if session_id is None:
        return []
    return await database.get_history(session_id)


@app.get("/history/{history_id}")
async def history_item(history_id: UUID) -> HistoryEntry:
    item = await database.get_history_item(str(history_id))
    if item is None:
        raise HTTPException(404, "History item not found")
    return item


@app.delete("/history/{history_id}", status_code=204)
async def delete_history(
    history_id: UUID,
    session_id: Annotated[str | None, Cookie()] = None,
) -> None:
    if session_id is None:
        raise HTTPException(401, "Session ID is required")
    if not await database.delete_history(session_id, str(history_id)):
        raise HTTPException(404, "History item not found")

@app.get("/health/")
async def health() -> JSONResponse:
    data = {"status": "active"}
    return JSONResponse(content=jsonable_encoder(data))
