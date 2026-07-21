"""Frontend assets and authored scam-library API routes."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path as ApiPath
from fastapi.responses import FileResponse
from pydantic import TypeAdapter

from .schema import ScamType, ScamTypeGroup


# This router owns both the authored scam-type catalog and explicit asset files.
router = APIRouter()
frontend_directory = Path(__file__).parent.parent / "frontend"
catalog_file = Path(__file__).with_name("data") / "scam_types.json"
# Validate the catalog at import time so bad data fails early during startup.
scam_type_catalog = tuple(
    TypeAdapter(list[ScamType]).validate_python(
        json.loads(catalog_file.read_text(encoding="utf-8"))
    )
)


def list_scam_types(group: ScamTypeGroup | None = None) -> list[ScamType]:
    """Return the full catalog or one filtered scam group."""
    return [
        item
        for item in scam_type_catalog
        if group is None or item.group == group
    ]


def get_scam_type(scam_type_id: str) -> ScamType | None:
    """Return one authored scam type by ID."""
    return next(
        (item for item in scam_type_catalog if item.id == scam_type_id),
        None,
    )


@router.get("/scam-types", response_model=list[ScamType])
async def scam_types(group: ScamTypeGroup | None = None) -> list[ScamType]:
    """Public catalog list endpoint used by the library page."""
    return list_scam_types(group)


@router.get("/scam-types/{scam_type_id}", response_model=ScamType)
async def scam_type(
    scam_type_id: Annotated[str, ApiPath(pattern=r"^[a-z0-9-]{1,80}$")],
) -> ScamType:
    """Public detail endpoint for one authored scam type."""
    item = get_scam_type(scam_type_id)
    if item is None:
        raise HTTPException(404, "Scam type not found")
    return item


def frontend_file(name: str) -> FileResponse:
    """Serve one explicit frontend asset without mounting the directory."""
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


@router.get("/app-data.js", include_in_schema=False)
async def frontend_app_data() -> FileResponse:
    return frontend_file("app-data.js")


@router.get("/app-render.js", include_in_schema=False)
async def frontend_app_render() -> FileResponse:
    return frontend_file("app-render.js")


@router.get("/service-worker.js", include_in_schema=False)
async def frontend_service_worker() -> FileResponse:
    return FileResponse(
        frontend_directory / "service-worker.js",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@router.get("/scamcheck-logo.png", include_in_schema=False)
async def frontend_logo() -> FileResponse:
    return frontend_file("scamcheck-logo.png")


@router.get("/detective-avatar.png", include_in_schema=False)
async def frontend_detective_avatar() -> FileResponse:
    return frontend_file("detective-avatar.png")


@router.get("/psychologist-avatar.png", include_in_schema=False)
async def frontend_psychologist_avatar() -> FileResponse:
    return frontend_file("psychologist-avatar.png")
