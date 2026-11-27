from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_ingest_settings
from app.core.config import IngestSettings
from app.schemas.features import Features

router = APIRouter()


@router.get("/features")
async def features(settings: Annotated[IngestSettings, Depends(get_ingest_settings)]) -> Features:
    return Features(uploads_enabled=settings.allow_uploads)
