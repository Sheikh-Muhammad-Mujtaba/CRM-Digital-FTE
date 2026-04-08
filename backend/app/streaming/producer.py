import os
import json
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

INTAKE_TOPIC = os.getenv("KAFKA_INTAKE_TOPIC", "fte.inbound")

conf = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
    "acks": "all",
}

producer = Producer(conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def publish_event(topic: str, event_data: dict):
    key = (
        event_data.get("customer_email")
        or event_data.get("customer_phone")
        or event_data.get("customer_id")
        or event_data.get("event_id")
        or "none"
    )
    producer.produce(
        topic,
        key=str(key),
        value=json.dumps(event_data).encode("utf-8"),
        callback=delivery_report,
    )
    producer.poll(0)
    producer.flush(timeout=10)


def publish_intake(event_data: dict):
    """Publish to the unified FTE intake topic (see specs/customer-success-fte-spec.md)."""
    publish_event(INTAKE_TOPIC, event_data)
