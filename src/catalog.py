"""Static scam catalog data."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from .schemas import ScamType, ScamTypeGroup


DATA_DIRECTORY = Path(__file__).with_name("data")
SCAM_TYPES = tuple(
    TypeAdapter(list[ScamType]).validate_python(
        json.loads((DATA_DIRECTORY / "scam_types.json").read_text(encoding="utf-8"))
    )
)


def list_scam_types(group: ScamTypeGroup | None = None) -> list[ScamType]:
    return [item for item in SCAM_TYPES if group is None or item.group == group]


def get_scam_type(scam_type_id: str) -> ScamType | None:
    return next((item for item in SCAM_TYPES if item.id == scam_type_id), None)
