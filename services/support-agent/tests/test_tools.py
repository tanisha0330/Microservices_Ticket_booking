from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app import tools

pytestmark = pytest.mark.asyncio

FUTURE_EVENT_DATE = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
NEAR_EVENT_DATE = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

BOOKING = {
    "id": "b1",
    "user_id": "u1",
    "event_id": "e1",
    "status": "CONFIRMED",
    "total_amount": "100.00",
    "currency": "USD",
}


@patch("app.tools.clients.get_event", new_callable=AsyncMock)
@patch("app.tools.clients.get_booking", new_callable=AsyncMock)
async def test_check_refund_eligibility_full_refund(mock_get_booking, mock_get_event):
    mock_get_booking.return_value = BOOKING
    mock_get_event.return_value = {"event_date": FUTURE_EVENT_DATE, "status": "PUBLISHED"}

    result = await tools.check_refund_eligibility("b1", "token")

    assert result["refund_percentage"] == 100
    assert result["eligible_amount"] == 100.0


@patch("app.tools.clients.get_event", new_callable=AsyncMock)
@patch("app.tools.clients.get_booking", new_callable=AsyncMock)
async def test_check_refund_eligibility_downstream_failure_raises(mock_get_booking, mock_get_event):
    mock_get_booking.side_effect = httpx.ConnectError("boom")

    with pytest.raises(tools.DownstreamError):
        await tools.check_refund_eligibility("b1", "token")


@patch("app.tools.clients.refund_payment", new_callable=AsyncMock)
@patch("app.tools.clients.get_payment_by_booking", new_callable=AsyncMock)
@patch("app.tools.clients.get_event", new_callable=AsyncMock)
@patch("app.tools.clients.get_booking", new_callable=AsyncMock)
async def test_request_refund_uses_rules_engine_amount_not_user_amount(
    mock_get_booking, mock_get_event, mock_get_payment, mock_refund, db_session
):
    """User asks for $1000 refund on a 24h-window booking (0% eligible) —
    must NOT trust the user amount, must use the rules-engine amount."""
    mock_get_booking.return_value = BOOKING
    mock_get_event.return_value = {"event_date": NEAR_EVENT_DATE, "status": "PUBLISHED"}
    mock_get_payment.return_value = {"payment_id": "p1", "booking_id": "b1", "amount": 100.0, "currency": "USD", "status": "SUCCEEDED"}

    result = await tools.request_refund(
        db_session, booking_id="b1", amount=1000.0, user_id="u1", user_bearer_token="token"
    )

    assert result["success"] is False
    assert result["eligible_amount"] == 0
    mock_refund.assert_not_called()


@patch("app.tools.clients.refund_payment", new_callable=AsyncMock)
@patch("app.tools.clients.get_payment_by_booking", new_callable=AsyncMock)
@patch("app.tools.clients.get_event", new_callable=AsyncMock)
@patch("app.tools.clients.get_booking", new_callable=AsyncMock)
async def test_request_refund_full_window_calls_provider_with_eligible_amount(
    mock_get_booking, mock_get_event, mock_get_payment, mock_refund, db_session
):
    mock_get_booking.return_value = BOOKING
    mock_get_event.return_value = {"event_date": FUTURE_EVENT_DATE, "status": "PUBLISHED"}
    mock_get_payment.return_value = {"payment_id": "p1", "booking_id": "b1", "amount": 100.0, "currency": "USD", "status": "SUCCEEDED"}
    mock_refund.return_value = {"id": "r1", "payment_id": "p1", "amount": "100.00", "status": "SUCCEEDED"}

    # user asks for a different (lower) amount than the eligible 100.0
    result = await tools.request_refund(
        db_session, booking_id="b1", amount=10.0, user_id="u1", user_bearer_token="token"
    )

    assert result["success"] is True
    assert result["eligible_amount"] == 100.0
    assert result["discrepancy_note"] is not None
    mock_refund.assert_awaited_once_with("p1", 100.0, "Full refund window")


@patch("app.tools.clients.search_policy_docs", new_callable=AsyncMock)
async def test_search_policy_no_results(mock_search):
    mock_search.return_value = {"results": []}
    result = await tools.search_policy("what is your policy")
    assert result["found"] is False


@patch("app.tools.clients.search_policy_docs", new_callable=AsyncMock)
async def test_search_policy_returns_top_result(mock_search):
    mock_search.return_value = {"results": [{"chunk_id": "c1", "content": "Refunds within 7 days...", "category": "support", "source": "s", "score": 0.9, "metadata": {}}]}
    result = await tools.search_policy("what is your refund policy")
    assert result["found"] is True
    assert "Refunds" in result["answer"]


async def test_escalate_to_human_creates_ticket_when_none_exists(db_session):
    ticket = await tools.escalate_to_human(db_session, "conv-1", "no policy match", user_id="u1")
    assert ticket.status == "ESCALATED"
    assert ticket.conversation_id == "conv-1"
