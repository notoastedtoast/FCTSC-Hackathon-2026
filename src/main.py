from typing import Annotated
from uuid import UUID, uuid4
from contextlib import asynccontextmanager
import hashlib
import hmac
import logging
import json
import re

from fastapi import Body, Cookie, Depends, FastAPI, HTTPException, Request, Response
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from .database import HistoryDatabase, HistoryEntry
from .deterministic_checker import check_message
from .frontend import router as frontend_router
from .schema import (
    DETECTIVE,
    GUIDE,
    RESPONDER,
    Analysis,
    GuideOutput,
    ResponderOutput,
    ResponderRequest,
    Settings,
    TELEPHONES,
)
from .wrapper import GeminiWrapper

logger = logging.getLogger(__name__)

# --- App boot and shared services -------------------------------------------------

# Deployment fix: local `.env` is optional because platforms like Vercel inject
# environment variables without creating a file on disk. We must not exit just
# because the file itself is absent.
load_dotenv(override=True)

settings = Settings.from_environment()
client = GeminiWrapper.from_settings(settings)
CALL_COUNT_COOKIE = "ai_call_count"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def get_client() -> GeminiWrapper:
    return client


ClientDep = Annotated[GeminiWrapper, Depends(get_client)]

# --- Session quota helpers --------------------------------------------------------

async def get_database(request: Request) -> HistoryDatabase:
    database: HistoryDatabase = request.app.state.database
    return await database.connect()


DatabaseDep = Annotated[HistoryDatabase, Depends(get_database)]

def _call_count(session_id: str, cookie: str | None) -> int:
    if cookie is None:
        return 0
    try:
        count, signature = cookie.split(".", 1)
        value = int(count)
    except ValueError:
        return 0
    expected = hmac.new(
        settings.session_cookie_secret.encode(),
        f"{session_id}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return value if value >= 0 and hmac.compare_digest(signature, expected) else 0


def consume_ai_call(response: Response, session_id: str | None, cookie: str | None) -> str:
    if session_id is None:
        session_id = str(uuid4())
        response.set_cookie("session_id", session_id, httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE)
    calls = _call_count(session_id, cookie)
    if calls >= settings.ai_session_call_limit:
        raise HTTPException(429, "AI session call limit reached")
    calls += 1
    signature = hmac.new(
        settings.session_cookie_secret.encode(),
        f"{session_id}:{calls}".encode(),
        hashlib.sha256,
    ).hexdigest()
    response.set_cookie(
        CALL_COUNT_COOKIE, f"{calls}.{signature}", httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE
    )
    return session_id


# --- FastAPI lifecycle ------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    database: HistoryDatabase = application.state.database
    await database.connect()
    try:
        yield
    finally:
        await database.close()
        await client.close()


app = FastAPI(lifespan=lifespan)
app.state.database = HistoryDatabase(":memory:")
app.include_router(frontend_router)


# --- API routes ------------------------------------------------------------------

# Main analysis entrypoint: run deterministic checks, call the Detective model,
# then save the finished result into history for later review.
@app.post("/analyze/")
async def analyze(
    client: ClientDep,
    database: DatabaseDep,
    response: Response,
    data: Annotated[str, Body(...)],
    session_id: Annotated[str | None, Cookie()] = None,
    ai_call_count: Annotated[str | None, Cookie(alias=CALL_COUNT_COOKIE)] = None,
) -> Analysis:
    session_id = consume_ai_call(response, session_id, ai_call_count)
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
    result.id = UUID(await database.save_analysis(session_id, data, result))
    return result


# Optional follow-up guide for suspicious or risky results.
@app.post(
    "/guide/",
    response_model=GuideOutput,
    responses={204: {"description": "Guide unavailable for low-risk analysis"}},
)
async def guide(
    client: ClientDep,
    database: DatabaseDep,
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


# Post-analysis responder: generate urgent next steps using only approved
# hotline numbers and previously saved analysis context.
@app.post("/responder/", response_model=ResponderOutput)
async def responder(client: ClientDep, database: DatabaseDep, data: ResponderRequest) -> ResponderOutput:
    item = await database.get_history_item(str(data.history_id))

    if item is None:
        raise HTTPException(404, "History item not found")

    stored = Analysis.model_validate(item["analysis"])

    if stored.analysis is None or stored.risk_level == "low":
        raise HTTPException(409, "A non-low-risk analysis is required")

    hotlines = {name: number for name, number in data.hotlines.items() if TELEPHONES.get(name) == number}
    bank = data.bank if data.bank in hotlines else None
    context = json.dumps({"choice": data.choice, "analysis": stored.analysis.model_dump(), "hotlines": hotlines, "police_hotline": TELEPHONES["Công an"], "selected_bank": bank}, ensure_ascii=False)

    try:
        output = await client.generate(RESPONDER, context)
        numbers = {re.sub(r"\D", "", value) for value in re.findall(r"\d(?:[\s.-]?\d){2,}", " ".join(output.steps))}
        if not numbers <= set(TELEPHONES.values()):
            raise ValueError("Responder output included an unknown phone number")
        await database.save_responder_output(str(data.history_id), output.model_dump_json())
        return output
    except Exception as e:
        logger.exception("Gemini responder generation failed with exception %s", e)
        raise HTTPException(502, "AI responder generation failed") from e


# Session-scoped history list used by the History page in the frontend.
@app.get("/history/")
async def history(
    database: DatabaseDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> list[HistoryEntry]:
    if session_id is None:
        return []
    return await database.get_history(session_id)


# Public fetch for one saved result by UUID. The frontend uses this for
# result-page deep links and history review.
@app.get("/history/{history_id}")
async def history_item(history_id: UUID, database: DatabaseDep) -> HistoryEntry:
    item = await database.get_history_item(str(history_id))
    if item is None:
        raise HTTPException(404, "History item not found")
    return item


# Delete only the current session's saved history item.
@app.delete("/history/{history_id}", status_code=204)
async def delete_history(
    history_id: UUID,
    database: DatabaseDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> None:
    if session_id is None:
        raise HTTPException(401, "Session ID is required")
    if not await database.delete_history(session_id, str(history_id)):
        raise HTTPException(404, "History item not found")


# Minimal health check for deployment smoke tests.
@app.get("/health/")
async def health() -> JSONResponse:
    data = {"status": "active"}
    return JSONResponse(content=jsonable_encoder(data))
