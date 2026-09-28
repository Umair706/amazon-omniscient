"""Schemas for agent-written artifacts (plans, notes, watchlists)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreate(BaseModel):
    """Payload to save an artifact."""

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    kind: str = Field(default="plan", max_length=30)
    niche_id: int | None = None
    data: dict | None = None


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int | None = None
    kind: str
    title: str
    content: str
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]
    total: int
