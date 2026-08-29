import pytest

from app.itinerary_builder import build_itinerary, fetch_rag_snippet


@pytest.mark.asyncio
async def test_rag_call_degrades_gracefully_when_unreachable():
    # Port 8010 is not running during tests -> must return None, not raise.
    result = await fetch_rag_snippet("http://localhost:8010", "Paris")
    assert result is None


@pytest.mark.asyncio
async def test_build_itinerary_end_to_end_without_rag():
    items, days, response_text = await build_itinerary(
        destination="Paris",
        start_date="2026-09-10",
        end_date="2026-09-12",
        interests=["food"],
        dietary_restrictions=["vegetarian"],
        rag_service_url="http://localhost:8010",
    )
    assert len(days) == 3  # 3 days inclusive
    assert len(items) == 3 * 5  # 5 slots/day
    assert "Paris" in response_text
    assert "vegetarian" in response_text.lower()
