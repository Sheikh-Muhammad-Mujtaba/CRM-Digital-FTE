import os


def business_identity_block() -> str:
    name = os.getenv("BUSINESS_NAME", "Softech Global Services")
    focus = os.getenv(
        "BUSINESS_FOCUS",
        "ERP solution services, ERPNext implementation, AI MCP integration with ERP systems, AI automation, and AI agent solutions for business operations.",
    )
    return (
        f"You represent **{name}**, a business technology services provider. "
        f"Core focus: {focus} "
        "Align every answer with this positioning. Do not claim partnerships or certifications unless they appear in the knowledge base."
    )
