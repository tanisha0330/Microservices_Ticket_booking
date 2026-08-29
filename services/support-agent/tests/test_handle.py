from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = pytest.mark.asyncio


@patch("app.tools.clients.get_booking", new_callable=AsyncMock)
async def test_handle_booking_inquiry_with_booking_id(mock_get_booking, client):
    mock_get_booking.return_value = {
        "id": "b1",
        "event_id": "e1",
        "status": "CONFIRMED",
        "total_amount": "100.00",
        "currency": "USD",
    }
    resp = await client.post(
        "/handle",
        json={
            "conversation_id": "conv-1",
            "user_id": "u1",
            "message": "What's the status of booking 3fa85f64-5717-4562-b3fc-2c963f66afa6?",
            "intent": "BOOKING_INQUIRY",
            "user_bearer_token": "tok",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "CONFIRMED" in body["response_text"]
    assert body["escalated"] is False


@patch("app.tools.clients.get_booking", new_callable=AsyncMock)
async def test_handle_downstream_failure_escalates_gracefully(mock_get_booking, client):
    mock_get_booking.side_effect = httpx.ConnectError("booking-service unreachable")

    resp = await client.post(
        "/handle",
        json={
            "conversation_id": "conv-2",
            "user_id": "u1",
            "message": "What's the status of booking 3fa85f64-5717-4562-b3fc-2c963f66afa6?",
            "intent": "BOOKING_INQUIRY",
            "user_bearer_token": "tok",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is True
    assert body["ticket_id"] is not None


@patch("app.tools.clients.search_policy_docs", new_callable=AsyncMock)
async def test_handle_booking_inquiry_no_id_searches_policy(mock_search, client):
    mock_search.return_value = {"results": []}
    resp = await client.post(
        "/handle",
        json={
            "conversation_id": "conv-3",
            "user_id": "u1",
            "message": "What is your refund policy in general?",
            "intent": "BOOKING_INQUIRY",
            "user_bearer_token": "tok",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is True
    assert "escalate" in body["response_text"].lower()


async def test_handle_refund_request_no_booking_id_asks_for_it(client):
    resp = await client.post(
        "/handle",
        json={
            "conversation_id": "conv-4",
            "user_id": "u1",
            "message": "I want a refund",
            "intent": "REFUND_REQUEST",
            "user_bearer_token": "tok",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalated"] is False
    assert "booking" in body["response_text"].lower()


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
