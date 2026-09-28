"""Artifacts an LLM agent writes back — business plans, notes, watchlists.

Lets an agent persist its own work in Omniscient so it survives across sessions
and isn't bound by the agent's context window. Optionally linked to a niche."""

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AgentArtifact(TimestampMixin, Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Keep the artifact if its niche is deleted; just unlink it.
    niche_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("niches.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False, server_default="plan")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional structured payload alongside the human-readable content.
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
