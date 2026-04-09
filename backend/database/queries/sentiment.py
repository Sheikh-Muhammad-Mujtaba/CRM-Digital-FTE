from __future__ import annotations

from typing import Literal

INBOUND_SENDERS = {"customer", "user", "human"}

POSITIVE_WORDS = {
    "thanks",
    "thank",
    "great",
    "good",
    "awesome",
    "perfect",
    "resolved",
    "helpful",
    "excellent",
    "appreciate",
}

NEGATIVE_WORDS = {
    "bad",
    "broken",
    "angry",
    "upset",
    "issue",
    "problem",
    "error",
    "failed",
    "frustrated",
    "refund",
    "urgent",
    "delay",
    "hate",
}


def is_inbound_sender(sender_type: str | None) -> bool:
    return (sender_type or "").lower() in INBOUND_SENDERS


def score_sentiment(content: str | None) -> tuple[str, float]:
    text = (content or "").lower()
    if not text.strip():
        return ("neutral", 0.0)

    tokens = [token.strip(".,!?;:()[]{}\"'`") for token in text.split() if token.strip()]
    if not tokens:
        return ("neutral", 0.0)

    positive = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    score = (positive - negative) / max(1, len(tokens))

    if score >= 0.08:
        return ("positive", round(score, 4))
    if score <= -0.08:
        return ("negative", round(score, 4))
    return ("neutral", round(score, 4))


def parse_final_sentiment_marker(content: str | None) -> Literal["positive", "neutral", "negative"] | None:
    """Parse system marker messages like: FINAL_SENTIMENT: positive."""
    text = (content or "").strip().lower()
    if not text.startswith("final_sentiment:"):
        return None

    value = text.split(":", 1)[1].strip()
    if value in {"positive", "neutral", "negative"}:
        return value
    return None


def sentiment_label_to_score(label: str) -> float:
    normalized = (label or "neutral").strip().lower()
    if normalized == "positive":
        return 1.0
    if normalized == "negative":
        return -1.0
    return 0.0
