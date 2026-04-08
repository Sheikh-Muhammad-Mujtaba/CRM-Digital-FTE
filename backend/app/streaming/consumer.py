import asyncio
import json
import logging
import os
import uuid

from confluent_kafka import Consumer, KafkaError, KafkaException
from dotenv import load_dotenv
from sqlalchemy import select

from app.agent.core import crm_agent
from app.agent.deps import AgentDependencies
from app.core.database import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from agents import Runner

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

INTAKE_TOPIC = os.getenv("KAFKA_INTAKE_TOPIC", "fte.inbound")


def create_consumer():
    conf = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        "group.id": os.getenv("KAFKA_CONSUMER_GROUP", "fte-message-processor"),
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    }
    return Consumer(conf)


async def _resolve_customer(session, msg_data: dict) -> Customer:
    """Identify or create customer by email (web, email) or phone (WhatsApp)."""
    email = (msg_data.get("customer_email") or "").strip() or None
    phone = (msg_data.get("customer_phone") or "").strip() or None

    if email:
        r = await session.execute(select(Customer).where(Customer.email == email))
        found = r.scalars().first()
        if found:
            return found
        c = Customer(
            name=msg_data.get("customer_name"),
            email=email,
            phone_number=phone,
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        return c

    if phone:
        r = await session.execute(select(Customer).where(Customer.phone_number == phone))
        found = r.scalars().first()
        if found:
            return found
        c = Customer(
            name=msg_data.get("customer_name"),
            email=None,
            phone_number=phone,
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        return c

    # Fallback: deterministic guest record for misconfigured producers
    placeholder = f"guest-{uuid.uuid4()}@intake.placeholder"
    c = Customer(
        name=msg_data.get("customer_name") or "Guest",
        email=placeholder,
        phone_number=None,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def process_message(msg_data: dict):
    channel = msg_data.get("channel", "unknown")
    logger.info("Processing event channel=%s", channel)

    async with AsyncSessionLocal() as session:
        customer = await _resolve_customer(session, msg_data)

        conv = Conversation(customer_id=customer.id)
        session.add(conv)
        await session.flush()

        user_msg = Message(
            conversation_id=conv.id,
            sender_type="user",
            content=msg_data.get("message") or "",
            channel=channel,
        )
        session.add(user_msg)
        await session.commit()
        await session.refresh(conv)

        deps = AgentDependencies(
            session=session,
            customer_id=str(customer.id),
            channel=channel,
            conversation_id=str(conv.id),
            customer_email=customer.email,
            customer_phone=customer.phone_number,
            customer_name=customer.name,
        )

        user_text = msg_data.get("message") or ""
        agent_input = (
            f"[Channel: {channel}; respond in the correct tone for this channel — "
            f"formal and complete for email/web, short and informal for whatsapp]\n\n"
            f"{user_text}"
        )

        try:
            await Runner.run(crm_agent, input=agent_input, context=deps)
            logger.info("[%s] Agent run finished.", channel)
        except Exception as e:
            logger.exception("Agent error: %s", e)


def run_consumer_loop(consumer, topics):
    consumer.subscribe(topics)
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            data = json.loads(msg.value().decode("utf-8"))

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(process_message(data))

    except KeyboardInterrupt:
        logger.info("Consumer shutting down (KeyboardInterrupt).")
    finally:
        consumer.close()


if __name__ == "__main__":
    c = create_consumer()
    logger.info("Kafka consumer subscribed to topic=%s group=%s", INTAKE_TOPIC, os.getenv("KAFKA_CONSUMER_GROUP"))
    run_consumer_loop(c, [INTAKE_TOPIC])
