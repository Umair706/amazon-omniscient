"""The artifacts route saves and reads agent-written plans/notes."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.artifacts import create_artifact, get_artifact
from app.models.agent_artifact import AgentArtifact
from app.schemas.artifact import ArtifactCreate


def _fake_db(existing: AgentArtifact | None = None):
    result = SimpleNamespace(scalar_one_or_none=lambda: existing)

    async def execute(*_a, **_k):
        return result

    async def flush():
        return None

    async def refresh(obj):
        # Simulate the DB assigning a primary key on insert.
        if getattr(obj, "id", None) is None:
            obj.id = 1

    return SimpleNamespace(execute=execute, add=lambda _o: None, flush=flush, refresh=refresh)


async def test_create_artifact_returns_saved_plan():
    payload = ArtifactCreate(title="Bean bag plan", content="Do X then Y", kind="plan", niche_id=1)
    res = await create_artifact(payload, db=_fake_db())
    assert res.id == 1
    assert res.title == "Bean bag plan"
    assert res.kind == "plan"
    assert res.niche_id == 1


async def test_get_missing_artifact_is_404():
    with pytest.raises(HTTPException) as raised:
        await get_artifact(999, db=_fake_db(existing=None))
    assert raised.value.status_code == 404


async def test_get_existing_artifact():
    art = AgentArtifact(id=5, title="Note", content="hello", kind="note", niche_id=None)
    res = await get_artifact(5, db=_fake_db(existing=art))
    assert res.id == 5
    assert res.kind == "note"
