import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    gemini_api_key: str
    cors_origins: list[str]
    kafka_bootstrap_servers: str
    kafka_intake_topic: str
    kafka_consumer_group: str
    gmail_webhook_secret: str | None
    gmail_pubsub_topic: str | None
    gmail_poll_enabled: bool
    gmail_poll_interval_seconds: int
    admin_username: str
    admin_password: str
    twilio_account_sid: str | None
    twilio_auth_token: str | None
    twilio_whatsapp_from: str | None


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Visit https://aistudio.google.com/app/apikeys to create a free API key."
        )

    return Settings(
        database_url=database_url,
        gemini_api_key=gemini_api_key,
        cors_origins=_split_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000")),
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        kafka_intake_topic=os.getenv("KAFKA_INTAKE_TOPIC", "fte.inbound"),
        kafka_consumer_group=os.getenv("KAFKA_CONSUMER_GROUP", "fte-message-processor"),
        gmail_webhook_secret=os.getenv("GMAIL_WEBHOOK_SECRET"),
        gmail_pubsub_topic=os.getenv("GMAIL_PUBSUB_TOPIC"),
        gmail_poll_enabled=_to_bool(os.getenv("GMAIL_POLL_ENABLED"), default=True),
        gmail_poll_interval_seconds=max(10, int(os.getenv("GMAIL_POLL_INTERVAL_SECONDS", "30"))),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "adminpass"),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_from=os.getenv("TWILIO_WHATSAPP_FROM"),
    )
