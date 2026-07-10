"""Small offline retriever that applies authorization before relevance scoring."""

import re
from collections.abc import Iterable

from agent_course.core import RunContext
from agent_course.rag.models import (
    DocumentChunk,
    RagAnswer,
    RagCitation,
    RetrievalHit,
)

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+")
_REFUSAL = "根据当前资料无法确认。"


def _tokens(text: str) -> frozenset[str]:
    return frozenset(token.casefold() for token in _TOKEN_PATTERN.findall(text))


def _overlap_score(query_tokens: frozenset[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(content)) / len(query_tokens)


def _has_enough_matching_terms(
    query_tokens: frozenset[str], content: str
) -> bool:
    matched_terms = len(query_tokens & _tokens(content))
    required_terms = min(2, len(query_tokens))
    return matched_terms >= required_terms


def _best_quote(content: str, query_tokens: frozenset[str]) -> str:
    candidates = [part.strip() for part in _SENTENCE_BOUNDARY.split(content)]
    candidates = [part for part in candidates if part]
    if not candidates:
        return content
    return max(
        enumerate(candidates),
        key=lambda item: (_overlap_score(query_tokens, item[1]), -item[0]),
    )[1]


class InMemoryRetriever:
    """Retrieve visible chunks with deterministic normalized query coverage."""

    def __init__(
        self,
        chunks: Iterable[DocumentChunk] = (),
        *,
        min_score: float = 0.5,
    ) -> None:
        if not 0 < min_score <= 1:
            raise ValueError("min_score must be greater than 0 and at most 1")
        self._chunks = tuple(chunks)
        self._min_score = min_score

    def search(
        self,
        query: str,
        context: RunContext,
        top_k: int,
    ) -> list[RetrievalHit]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        query_tokens = _tokens(query)
        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._chunks:
            if not self._is_visible(chunk, context):
                continue
            score = _overlap_score(query_tokens, chunk.content)
            if score >= self._min_score and _has_enough_matching_terms(
                query_tokens, chunk.content
            ):
                scored.append((score, chunk))

        scored.sort(key=lambda item: (-item[0], item[1].document_id, item[1].chunk_id))
        hits: list[RetrievalHit] = []
        for citation_id, (score, chunk) in enumerate(scored[:top_k], start=1):
            citation = RagCitation(
                citation_id=citation_id,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                quote=_best_quote(chunk.content, query_tokens),
            )
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    content=chunk.content,
                    score=score,
                    citation=citation,
                )
            )
        return hits

    def answer(
        self,
        query: str,
        context: RunContext,
        top_k: int = 3,
    ) -> RagAnswer:
        hits = self.search(query, context, top_k)
        if not hits:
            return RagAnswer(answer=_REFUSAL, refused=True)

        top_hit = hits[0]
        return RagAnswer(
            answer=f"{top_hit.citation.quote} [1]",
            citations=tuple(hit.citation for hit in hits),
        )

    @staticmethod
    def _is_visible(chunk: DocumentChunk, context: RunContext) -> bool:
        if chunk.tenant_id != context.tenant_id:
            return False
        user_allowed = (
            chunk.allowed_user_ids is None or context.user_id in chunk.allowed_user_ids
        )
        permissions_allowed = chunk.required_permissions <= context.permissions
        return user_allowed and permissions_allowed


__all__ = ["InMemoryRetriever"]
