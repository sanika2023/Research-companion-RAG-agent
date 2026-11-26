from pydantic import BaseModel


class Features(BaseModel):
    """What this server allows, so the frontend can hide what won't work."""

    uploads_enabled: bool
