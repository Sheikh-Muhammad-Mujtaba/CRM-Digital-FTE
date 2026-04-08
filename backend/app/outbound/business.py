import os

# Defaults match a generic B2B technology services provider; override via environment in production.


def business_identity_block() -> str:
    name = os.getenv("BUSINESS_NAME", "NexTech Services Group")
    focus = os.getenv(
        "BUSINESS_FOCUS",
        "managed IT, cloud platforms, network operations, cybersecurity advisory, and technical consulting for organizations.",
    )
    return (
        f"You represent **{name}**, a business technology services provider. "
        f"Core focus: {focus} "
        "Align every answer with this positioning. Do not claim partnerships or certifications unless they appear in the knowledge base."
    )
