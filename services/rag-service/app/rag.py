from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings import chunk_text, embed_text
from app.models import Document, DocumentChunk


async def ingest_document(
    db: AsyncSession, content: str, category: str, source: str, metadata: dict | None = None
) -> tuple[str, int]:
    """Chunk + embed a document and persist it. Used directly by both the
    POST /documents route and scripts/seed_rag.py (no HTTP round-trip needed
    for seeding)."""
    metadata = metadata or {}
    document = Document(content=content, category=category, source=source, doc_metadata=metadata)
    db.add(document)
    await db.flush()  # assigns document.id

    chunks = chunk_text(content)
    for index, chunk in enumerate(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                category=category,
                source=source,
                doc_metadata=metadata,
                embedding=embed_text(chunk),
            )
        )

    return str(document.id), len(chunks)


async def search_chunks(
    db: AsyncSession, query: str, category: str | None = None, top_k: int = 5
) -> list[dict]:
    """Cosine-distance nearest-neighbor search over document_chunks (pgvector
    `<=>` operator). Requires a real Postgres+pgvector backend."""
    query_embedding = embed_text(query)
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    stmt = select(DocumentChunk, distance.label("distance"))
    if category:
        stmt = stmt.where(DocumentChunk.category == category)
    stmt = stmt.order_by(distance).limit(top_k)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "chunk_id": str(chunk.id),
            "content": chunk.content,
            "category": chunk.category,
            "source": chunk.source,
            "score": 1.0 - distance_val,
            "metadata": chunk.doc_metadata,
        }
        for chunk, distance_val in rows
    ]
