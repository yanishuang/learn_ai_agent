"""Immutable models for deterministic, permission-aware retrieval."""

from pydantic import ConfigDict, Field, field_validator

from agent_course.core import FrozenModel


class RagModel(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DocumentChunk(RagModel):
    chunk_id: str
    document_id: str
    tenant_id: str
    title: str
    content: str
    allowed_user_ids: frozenset[str] | None = None
    required_permissions: frozenset[str] = frozenset()

    @field_validator("chunk_id", "document_id", "tenant_id", "title", "content")
    @classmethod
    def text_fields_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("document chunk fields must be nonblank")
        return value


class RagCitation(RagModel):
    citation_id: int = Field(ge=1)
    document_id: str
    chunk_id: str
    title: str
    quote: str


class RetrievalHit(RagModel):
    chunk_id: str
    document_id: str
    title: str
    content: str
    score: float = Field(ge=0, le=1)
    citation: RagCitation


class RagAnswer(RagModel):
    answer: str
    citations: tuple[RagCitation, ...] = ()
    refused: bool = False


__all__ = [
    "DocumentChunk",
    "RagAnswer",
    "RagCitation",
    "RetrievalHit",
]
