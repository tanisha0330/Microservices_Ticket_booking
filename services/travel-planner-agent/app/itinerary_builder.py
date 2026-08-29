"""
Template-based itinerary generation (no LLM). Assembles a day-by-day plan
from the mock external APIs plus a best-effort RAG lookup for destination
knowledge/citations.
"""
from datetime import date, timedelta

import httpx
import structlog

from app import mock_apis

log = structlog.get_logger()

PRICE_LEVEL_TO_COST = {1: 15, 2: 35, 3: 65, 4: 120}


async def fetch_rag_snippet(rag_service_url: str, destination: str) -> str | None:
    """Best-effort call to the RAG service. Returns None (never raises) if
    the service is unreachable — graceful degradation per spec."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{rag_service_url}/search",
                json={"query": f"{destination} travel", "category": "travel", "top_k": 3},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None
            snippets = [r["content"] for r in results[:2] if r.get("content")]
            return " ".join(snippets) if snippets else None
    except Exception as exc:
        log.warning("rag_service_unavailable", error=str(exc))
        return None


def _date_range(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        end = start
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _build_day(destination: str, day_str: str, day_number: int, interests: list[str]) -> tuple[list[dict], dict]:
    weather = mock_apis.get_weather(destination, day_str)
    places = mock_apis.get_places(destination, "attraction", limit=3)
    events = mock_apis.get_events(destination, day_str)
    restaurants = mock_apis.get_restaurants(destination, price="$$")

    items = []

    morning_place = places[0]
    items.append(
        {
            "day_number": day_number,
            "time_slot": "Morning",
            "activity_type": "ACTIVITY",
            "title": morning_place["name"],
            "description": morning_place["description"],
            "location": destination,
            "cost_estimate": PRICE_LEVEL_TO_COST[morning_place["price_level"]],
            "booking_url": None,
            "source_reference": "mock_places API",
        }
    )

    lunch = restaurants[0]
    items.append(
        {
            "day_number": day_number,
            "time_slot": "Lunch",
            "activity_type": "RESTAURANT",
            "title": lunch["name"],
            "description": f"{lunch['cuisine']} cuisine, rated {lunch['rating']}/5.",
            "location": destination,
            "cost_estimate": len(lunch["price"]) * 20,
            "booking_url": None,
            "source_reference": "mock_restaurants API",
        }
    )

    afternoon_place = places[1 % len(places)]
    items.append(
        {
            "day_number": day_number,
            "time_slot": "Afternoon",
            "activity_type": "ACTIVITY",
            "title": afternoon_place["name"],
            "description": (
                f"{afternoon_place['description']} "
                f"Weather forecast: {weather['condition']}, {weather['temperature']}C."
            ),
            "location": destination,
            "cost_estimate": PRICE_LEVEL_TO_COST[afternoon_place["price_level"]],
            "booking_url": None,
            "source_reference": "mock_places API + mock_weather API",
        }
    )

    dinner = restaurants[1 % len(restaurants)]
    items.append(
        {
            "day_number": day_number,
            "time_slot": "Dinner",
            "activity_type": "RESTAURANT",
            "title": dinner["name"],
            "description": f"{dinner['cuisine']} cuisine, rated {dinner['rating']}/5.",
            "location": destination,
            "cost_estimate": len(dinner["price"]) * 20,
            "booking_url": None,
            "source_reference": "mock_restaurants API",
        }
    )

    if events:
        event = events[0]
        items.append(
            {
                "day_number": day_number,
                "time_slot": "Evening",
                "activity_type": "EVENT",
                "title": event["name"],
                "description": f"{event['description']} Starts at {event['time']}.",
                "location": destination,
                "cost_estimate": 0,
                "booking_url": None,
                "source_reference": "mock_events API",
            }
        )
    else:
        evening_place = places[2 % len(places)]
        items.append(
            {
                "day_number": day_number,
                "time_slot": "Evening",
                "activity_type": "ACTIVITY",
                "title": f"Free evening — optional visit to {evening_place['name']}",
                "description": evening_place["description"],
                "location": destination,
                "cost_estimate": PRICE_LEVEL_TO_COST[evening_place["price_level"]],
                "booking_url": None,
                "source_reference": "mock_places API",
            }
        )

    day_summary = {
        "day_number": day_number,
        "date": day_str,
        "weather": weather,
        "items": items,
    }
    return items, day_summary


async def build_itinerary(
    destination: str,
    start_date: str,
    end_date: str,
    interests: list[str] | None,
    dietary_restrictions: list[str] | None,
    rag_service_url: str,
) -> tuple[list[dict], list[dict], str]:
    """Returns (item_dicts_for_persistence, day_summaries_for_response, response_text)."""
    interests = interests or []
    day_strs = _date_range(start_date, end_date)

    all_items: list[dict] = []
    day_summaries: list[dict] = []
    for i, day_str in enumerate(day_strs, start=1):
        items, summary = _build_day(destination, day_str, i, interests)
        all_items.extend(items)
        day_summaries.append(summary)

    rag_snippet = await fetch_rag_snippet(rag_service_url, destination)

    lines = [f"Here's your {len(day_strs)}-day itinerary for {destination}:"]
    if rag_snippet:
        lines.append(f"\n{rag_snippet} (source: RAG destination knowledge)")
    for summary in day_summaries:
        lines.append(f"\nDay {summary['day_number']} ({summary['date']}) — {summary['weather']['condition']}, {summary['weather']['temperature']}C:")
        for item in summary["items"]:
            lines.append(f"  {item['time_slot']}: {item['title']} (~${item['cost_estimate']}, source: {item['source_reference']})")
    if dietary_restrictions:
        lines.append(f"\nDietary restrictions noted: {', '.join(dietary_restrictions)}.")

    return all_items, day_summaries, "\n".join(lines)
