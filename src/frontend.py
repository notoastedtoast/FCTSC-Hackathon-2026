"""Frontend assets and authored scam-library API routes."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path as ApiPath
from fastapi.responses import FileResponse

from .catalog import get_scam_type, list_scam_types
from .schema import ScamType, ScamTypeGroup


router = APIRouter()
frontend_directory = Path(__file__).parent.parent / "frontend"


@router.get("/scam-types", response_model=list[ScamType])
async def scam_types(group: ScamTypeGroup | None = None) -> list[ScamType]:
    return list_scam_types(group)


@router.get("/scam-types/{scam_type_id}", response_model=ScamType)
async def scam_type(
    scam_type_id: Annotated[str, ApiPath(pattern=r"^[a-z0-9-]{1,80}$")],
) -> ScamType:
    item = get_scam_type(scam_type_id)
    if item is None:
        raise HTTPException(404, "Scam type not found")
    return item


def frontend_file(name: str) -> FileResponse:
    return FileResponse(frontend_directory / name)


@router.get("/", include_in_schema=False)
async def frontend_index() -> FileResponse:
    return frontend_file("index.html")


@router.get("/styles.css", include_in_schema=False)
async def frontend_styles() -> FileResponse:
    return frontend_file("styles.css")


@router.get("/offline-analyzer.js", include_in_schema=False)
async def frontend_offline_analyzer() -> FileResponse:
    return frontend_file("offline-analyzer.js")


@router.get("/app.js", include_in_schema=False)
async def frontend_app() -> FileResponse:
    return frontend_file("app.js")


@router.get("/service-worker.js", include_in_schema=False)
async def frontend_service_worker() -> FileResponse:
    return frontend_file("service-worker.js")


@router.get("/scamcheck-logo.png", include_in_schema=False)
async def frontend_logo() -> FileResponse:
    return frontend_file("scamcheck-logo.png")
