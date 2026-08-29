"""Idempotency self-check: the same envelope delivered twice is only processed once."""
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.consumer import handle_envelope, process_message
from app.models import Notification

pytestmark = pytest.mark.asyncio


def _envelope(event_id: str, booking_id: str, user_id: str, event_type="BOOKING_CONFIRMED"):
    return {
        "schema_version": 1,
        "event_type": event_type,
        "event_id": event_id,
        "occurred_at": "2026-08-30T00:00:00+00:00",
        "payload": {
            "booking_id": booking_id,
            "user_id": user_id,
            "status": "CONFIRMED",
        },
    }


async def test_handle_envelope_creates_notification(db_session):
    envelope = _envelope(str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()))
    await handle_envelope(db_session, envelope)

    result = await db_session.execute(select(Notification))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].event_type == "BOOKING_CONFIRMED"


async def test_duplicate_delivery_is_processed_once(db_session):
    event_id = str(uuid.uuid4())
    envelope = _envelope(event_id, str(uuid.uuid4()), str(uuid.uuid4()))

    await handle_envelope(db_session, envelope)
    await handle_envelope(db_session, envelope)  # redelivered, same event_id

    result = await db_session.execute(select(Notification))
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_unhandled_event_type_marks_processed_without_notification(db_session):
    envelope = _envelope(
        str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), event_type="SEATS_LOCKED"
    )
    await handle_envelope(db_session, envelope)

    result = await db_session.execute(select(Notification))
    assert result.scalars().all() == []


async def test_process_message_routes_to_dlq_after_max_retries(db_session):
    envelope = _envelope(str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()))
    value = json.dumps(envelope).encode("utf-8")
    key = b"some-key"
    producer = AsyncMock()

    with (
        patch("app.consumer.handle_envelope", AsyncMock(side_effect=RuntimeError("boom"))),
        patch("app.consumer.asyncio.sleep", AsyncMock()),
    ):
        await process_message(producer, value, key)

    producer.send_and_wait.assert_awaited_once_with("booking.events.dlq", value=value, key=key)
