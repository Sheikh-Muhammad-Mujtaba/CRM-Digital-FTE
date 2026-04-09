def format_for_channel(channel: str, text: str) -> str:
    normalized = (channel or "").lower()
    if normalized == "whatsapp":
        return text.strip()[:400]
    return text.strip()
