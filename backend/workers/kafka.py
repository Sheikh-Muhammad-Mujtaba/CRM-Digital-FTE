import json
import logging

from confluent_kafka import Consumer, Producer

from settings import get_settings

logger = logging.getLogger(__name__)


def _delivery_report(err, msg):
    if err is not None:
        logger.error("Message delivery failed: %s", err)


def create_producer() -> Producer:
    settings = get_settings()
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "acks": "all",
    }
    return Producer(conf)


def publish_event(producer: Producer, topic: str, event_data: dict):
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
        callback=_delivery_report,
    )
    producer.poll(0)
    producer.flush(timeout=10)


def create_consumer() -> Consumer:
    settings = get_settings()
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": settings.kafka_consumer_group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
    return Consumer(conf)
