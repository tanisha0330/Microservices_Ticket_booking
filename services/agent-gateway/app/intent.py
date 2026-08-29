"""
intent.py
~~~~~~~~~
Deterministic keyword/regex heuristic intent classifier.

No real LLM exists in this project (no API keys anywhere) — this stands in
for the CLASSIFICATION_PROMPT LLM call described in phase3_prompt.md.
Checked in priority order below; the first matching intent wins.

ponytail: naive keyword heuristic, ceiling is ambiguous/compound messages
("I want a refund but also plan me a trip" -> only REFUND_REQUEST fires).
Upgrade path: swap in a real LLM classifier behind the same
`classify(text) -> dict` signature when one is available.
"""
import re

INTENTS = [
    "TRAVEL_PLANNING",
    "BOOKING_INQUIRY",
    "REFUND_REQUEST",
    "GENERAL_QA",
    "CHITCHAT",
    "ESCALATION",
]

_ESCALATION_PATTERNS = [
    r"\bhuman\b", r"\bagent\b", r"\brepresentative\b", r"\breal person\b", r"\bspeak to someone\b",
]
_REFUND_PATTERNS = [
    r"\brefund\b", r"\bmoney back\b", r"\breimburse", r"\bcharge ?back\b",
]
_BOOKING_PATTERNS = [
    r"\bmy booking\b", r"\bbooking status\b", r"\bcancel my\b", r"\bmodify my booking\b",
    r"\breschedule\b", r"\bbooking id\b",
]
_TRAVEL_PATTERNS = [
    r"\bplan a trip\b", r"\bitinerary\b", r"\btravel to\b", r"\bvisit\b", r"\bthings to do\b",
    r"\bwhat to do in\b", r"\bvacation\b", r"\btrip to\b",
]
_CHITCHAT_PATTERNS = [
    r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bthanks\b", r"\bthank you\b", r"\bgood morning\b",
    r"\bgood evening\b",
]


def _matches(patterns: list[str], text_lower: str) -> list[str]:
    return [p for p in patterns if re.search(p, text_lower)]


def classify(message: str) -> dict:
    """Classify a message into one of INTENTS.

    Returns {"intent": str, "confidence": float, "reasoning": str}.
    """
    text_lower = message.lower()

    # Priority order matters: ESCALATION and REFUND are explicit asks that
    # should win over broader categories (e.g. "refund my trip booking").
    checks = [
        ("ESCALATION", _ESCALATION_PATTERNS),
        ("REFUND_REQUEST", _REFUND_PATTERNS),
        ("BOOKING_INQUIRY", _BOOKING_PATTERNS),
        ("TRAVEL_PLANNING", _TRAVEL_PATTERNS),
        ("CHITCHAT", _CHITCHAT_PATTERNS),
    ]
    for intent, patterns in checks:
        matched = _matches(patterns, text_lower)
        if matched:
            return {
                "intent": intent,
                "confidence": 0.9,
                "reasoning": f"Matched keyword pattern(s): {matched}",
            }

    return {
        "intent": "GENERAL_QA",
        "confidence": 0.5,
        "reasoning": "No specific intent keywords matched; defaulting to general Q&A.",
    }
