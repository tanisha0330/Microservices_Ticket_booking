"""Requires a real Postgres+pgvector connection (DATABASE_URL). Skipped
gracefully when unreachable -- vector cosine search (`<=>`) has no SQLite
equivalent, so it can't be covered by the unit tests above."""
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.database import Base
from app.rag import ingest_document, search_chunks

settings = get_settings()


@pytest_asyncio.fixture()
async def pg_session():
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("No live Postgres+pgvector connection available")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


async def test_search_returns_results_and_respects_category(pg_session):
    await ingest_document(
        pg_session, content="Refunds are full within 7 days.", category="support", source="policy"
    )
    await ingest_document(
        pg_session, content="Paris is a popular travel destination.", category="travel", source="guide"
    )
    await pg_session.commit()

    results = await search_chunks(pg_session, query="refund policy", category="support", top_k=5)
    assert len(results) >= 1
    assert all(r["category"] == "support" for r in results)
