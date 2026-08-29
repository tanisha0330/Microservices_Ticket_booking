import pytest

from app.intent import classify

CASES = [
    ("Plan a trip to Paris for 5 days", "TRAVEL_PLANNING"),
    ("What to do in Tokyo?", "TRAVEL_PLANNING"),
    ("What's my booking status?", "BOOKING_INQUIRY"),
    ("I want to cancel my booking", "BOOKING_INQUIRY"),
    ("I want a refund", "REFUND_REQUEST"),
    ("How do I get my money back?", "REFUND_REQUEST"),
    ("What events are happening this weekend?", "GENERAL_QA"),
    ("How does booking work on this site?", "GENERAL_QA"),
    ("Hello!", "CHITCHAT"),
    ("Thank you so much", "CHITCHAT"),
    ("I want to talk to a human", "ESCALATION"),
    ("Get me a representative", "ESCALATION"),
]


@pytest.mark.parametrize("message,expected", CASES)
def test_classify_intent(message, expected):
    result = classify(message)
    assert result["intent"] == expected
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["reasoning"], str)


def test_refund_wins_over_travel_wording():
    # "refund" should win priority over travel-sounding words per our
    # documented priority order (escalation > refund > booking > travel > chitchat).
    result = classify("I want a refund for my trip to Paris")
    assert result["intent"] == "REFUND_REQUEST"
