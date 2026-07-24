"""RAG retrieval: embed the caller's question, search the tenant's knowledge
chunks by cosine distance (pgvector HNSW index from migration 0001), and
return only chunks confident enough to ground an answer.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.core.db import tenant_session
from app.modules.conversation.models import KnowledgeChunk
from app.modules.conversation.providers.base import EmbeddingProvider

DEFAULT_TOP_K = 4
# pgvector cosine_distance is in [0, 2] (0 = identical direction). Chunks
# beyond this are treated as "no relevant answer" rather than grounding a
# guess — the primary defense against hallucinated FAQ answers (Risk R3).
MAX_RELEVANT_DISTANCE = 0.5


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    distance: float


async def retrieve_relevant_chunks(
    tenant_id: uuid.UUID,
    query: str,
    embeddings: EmbeddingProvider,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    [query_vector] = await embeddings.embed([query], for_query=True)

    async with tenant_session(tenant_id) as session:
        distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
        rows = (
            await session.execute(
                select(KnowledgeChunk.content, distance.label("distance"))
                .order_by(distance)
                .limit(top_k)
            )
        ).all()

    return [
        RetrievedChunk(content=row.content, distance=row.distance)
        for row in rows
        if row.distance <= MAX_RELEVANT_DISTANCE
    ]
