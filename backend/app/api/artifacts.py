"""API for agent-written artifacts — business plans, notes, watchlists.

Lets the MCP server (and the UI) save and retrieve an agent's own output so it
persists beyond a single agent session.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.agent_artifact import AgentArtifact
from app.schemas.artifact import ArtifactCreate, ArtifactListResponse, ArtifactResponse

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.post("/", response_model=ArtifactResponse, status_code=201)
async def create_artifact(payload: ArtifactCreate, db: AsyncSession = Depends(get_db)) -> ArtifactResponse:
    """Save a plan/note/watchlist. Optionally linked to a niche."""
    artifact = AgentArtifact(
        title=payload.title, content=payload.content, kind=payload.kind,
        niche_id=payload.niche_id, data=payload.data,
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)
    return ArtifactResponse.model_validate(artifact)


@router.get("/", response_model=ArtifactListResponse)
async def list_artifacts(
    niche_id: int | None = None,
    kind: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ArtifactListResponse:
    """List artifacts, newest first, optionally filtered by niche or kind."""
    stmt = select(AgentArtifact).order_by(AgentArtifact.created_at.desc())
    count_stmt = select(func.count()).select_from(AgentArtifact)
    if niche_id is not None:
        stmt = stmt.where(AgentArtifact.niche_id == niche_id)
        count_stmt = count_stmt.where(AgentArtifact.niche_id == niche_id)
    if kind is not None:
        stmt = stmt.where(AgentArtifact.kind == kind)
        count_stmt = count_stmt.where(AgentArtifact.kind == kind)

    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return ArtifactListResponse(
        items=[ArtifactResponse.model_validate(a) for a in items], total=total,
    )


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: int, db: AsyncSession = Depends(get_db)) -> ArtifactResponse:
    artifact = (
        await db.execute(select(AgentArtifact).where(AgentArtifact.id == artifact_id))
    ).scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    return ArtifactResponse.model_validate(artifact)


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(artifact_id: int, db: AsyncSession = Depends(get_db)) -> None:
    await db.execute(delete(AgentArtifact).where(AgentArtifact.id == artifact_id))
