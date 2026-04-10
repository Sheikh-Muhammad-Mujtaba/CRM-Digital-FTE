import asyncio
import json
import logging
import re
import uuid

from agents import Runner
from confluent_kafka import Consumer, KafkaError, KafkaException
from openai import RateLimitError
from sqlalchemy.exc import DBAPIError
from sqlalchemy import func, select

from agent.customer_success_agent import crm_agent
from agent.deps import AgentDependencies
from core.database import AsyncSessionLocal
from database.models.conversation import Conversation
from database.models.customer import Customer
from database.models.message import Message
from outbound.dispatch import dispatch_channel_reply
from settings import get_settings
from workers.kafka import create_consumer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _extract_retry_seconds(err: Exception) -> int | None:
    message = str(err)
    match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(float(match.group(1)))
    except ValueError:
        return None


async def _save_agent_fallback_message(
    conversation_id: str,
    channel: str,
    content: str,
    customer_email: str | None,
    customer_phone: str | None,
    ticket_id: str | None = None,
) -> None:
    final_content = content.strip()
    if ticket_id and "Ticket Tracking Number:" not in final_content:
        final_content = f"{final_content}\n\nTicket Tracking Number: {ticket_id}"

    async with AsyncSessionLocal() as fallback_session:
        fallback_session.add(
            Message(
                conversation_id=uuid.UUID(conversation_id),
                sender_type="agent",
                content=final_content,
                channel=channel,
            )
        )
        await fallback_session.commit()

    try:
        outbound_result = await dispatch_channel_reply(
            channel=channel,
            customer_email=customer_email,
            customer_phone=customer_phone,
            response_text=final_content,
        )
        logger.info("Fallback outbound dispatch result: %s", outbound_result)
    except Exception:
        logger.error("Failed to dispatch fallback rate-limit message", exc_info=True)


async def _resolve_customer(session, msg_data: dict) -> Customer:
    customer_id = (msg_data.get("customer_id") or "").strip() or None
    email = (msg_data.get("customer_email") or "").strip() or None
    phone = (msg_data.get("customer_phone") or "").strip() or None
    name = (msg_data.get("customer_name") or "").strip() or None

    # If upstream already knows the customer ID, use it first.
    if customer_id:
        try:
            parsed_id = uuid.UUID(customer_id)
            result = await session.execute(select(Customer).where(Customer.id == parsed_id))
            found = result.scalars().first()
            if found:
                if email and not found.email:
                    found.email = email
                if phone and not found.phone_number:
                    found.phone_number = phone
                if name and not found.name:
                    found.name = name
                await session.commit()
                await session.refresh(found)
                return found
        except ValueError:
            logger.warning("Invalid customer_id provided in event: %s", customer_id)

    if email:
        result = await session.execute(select(Customer).where(Customer.email == email))
        found = result.scalars().first()
        if found:
            if phone and not found.phone_number:
                found.phone_number = phone
                await session.commit()
                await session.refresh(found)
            return found

        # Cross-channel merge: if we have a unique named customer, attach email/phone there.
        if name and name.lower() not in {"whatsapp user", "guest", "email user"}:
            name_result = await session.execute(
                select(Customer).where(func.lower(Customer.name) == name.lower())
            )
            name_matches = name_result.scalars().all()
            if len(name_matches) == 1:
                merged = name_matches[0]
                if not merged.email:
                    merged.email = email
                if phone and not merged.phone_number:
                    merged.phone_number = phone
                await session.commit()
                await session.refresh(merged)
                return merged

        customer = Customer(name=name, email=email, phone_number=phone)
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer

    if phone:
        result = await session.execute(select(Customer).where(Customer.phone_number == phone))
        found = result.scalars().first()
        if found:
            if email and not found.email:
                found.email = email
                await session.commit()
                await session.refresh(found)
            return found

        if name and name.lower() not in {"whatsapp user", "guest", "email user"}:
            name_result = await session.execute(
                select(Customer).where(func.lower(Customer.name) == name.lower())
            )
            name_matches = name_result.scalars().all()
            if len(name_matches) == 1:
                merged = name_matches[0]
                if not merged.phone_number:
                    merged.phone_number = phone
                if email and not merged.email:
                    merged.email = email
                await session.commit()
                await session.refresh(merged)
                return merged

        customer = Customer(name=name, email=None, phone_number=phone)
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer

    customer = Customer(
        name=name or "Guest",
        email=f"guest-{uuid.uuid4()}@intake.placeholder",
        phone_number=None,
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


async def _find_active_conversation(session, customer_id: uuid.UUID) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(
            Conversation.customer_id == customer_id,
            Conversation.status.in_(["open", "escalated"]),
        )
        .order_by(Conversation.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _latest_human_handoff_instruction(session, conversation_id: uuid.UUID) -> str | None:
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_type == "system",
            Message.content.like("HUMAN_TO_AGENT:%"),
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    note = result.scalar_one_or_none()
    if note is None:
        return None
    return note.content.split(":", 1)[1].strip() if ":" in note.content else note.content


async def process_message(msg_data: dict) -> bool:
    """Process an inbound message with the AI agent.
    
    1. Resolve or create customer record
    2. Create new conversation
    3. Save incoming message
    4. Invoke OpenAI Agents SDK agent with dependencies
    5. Agent tools handle response and persistence
    
    Args:
        msg_data: Event data from Kafka (channel, message, customer_* fields)
        
    Raises:
        Exception: Propagated from agent execution
    """
    channel = msg_data.get("channel", "unknown")
    message_content = msg_data.get("message", "").strip()
    
    if not message_content:
        logger.warning("Received empty message from channel=%s", channel)
        return True
    
    for attempt in range(2):
        conv = None
        customer = None
        try:
            async with AsyncSessionLocal() as session:
                # Resolve customer
                customer = await _resolve_customer(session, msg_data)
                logger.info(
                    "Processing message for customer_id=%s via channel=%s",
                    customer.id,
                    channel,
                )

                # Reuse active conversation for the same customer so history/tickets remain linked.
                conv = await _find_active_conversation(session, customer.id)
                if conv is None:
                    conv = Conversation(customer_id=customer.id)
                    session.add(conv)
                    await session.flush()
                    logger.info("Created new conversation: customer_id=%s conversation_id=%s", customer.id, conv.id)
                else:
                    logger.info("Reusing active conversation: customer_id=%s conversation_id=%s status=%s", customer.id, conv.id, conv.status)

                session.add(
                    Message(
                        conversation_id=conv.id,
                        sender_type="customer",
                        content=message_content,
                        channel=channel,
                    )
                )
                await session.commit()

                # Human owns escalated conversations until admin explicitly hands off back to agent.
                if conv.status == "escalated":
                    logger.info(
                        "Conversation is escalated and human-owned; skipping agent run: conversation_id=%s",
                        conv.id,
                    )
                    return True

                # Prepare agent dependencies
                deps = AgentDependencies(
                    session=session,
                    customer_id=str(customer.id),
                    channel=channel,
                    conversation_id=str(conv.id),
                    customer_email=customer.email,
                    customer_phone=customer.phone_number,
                    customer_name=customer.name,
                )

                # Format input with channel context
                user_text = message_content
                handoff_instruction = await _latest_human_handoff_instruction(session, conv.id)

                agent_input = (
                    f"[Channel: {channel}; respond in the correct tone for this channel — "
                    "formal and complete for email/web, short and informal for whatsapp.]\n\n"
                    f"{user_text}"
                )
                if handoff_instruction:
                    agent_input = f"[Human instruction for this case: {handoff_instruction}]\n\n{agent_input}"

                # Run agent with dependencies injection
                logger.info(
                    "Invoking OpenAI Agents SDK agent: conversation_id=%s",
                    conv.id,
                )

                run_result = await Runner.run(crm_agent, input=agent_input, context=deps)

                agent_reply_exists = (
                    await session.execute(
                        select(Message.id)
                        .where(Message.conversation_id == conv.id, Message.sender_type == "agent")
                        .limit(1)
                    )
                ).first() is not None

                if not agent_reply_exists:
                    final_reply = getattr(run_result, "final_output", None)
                    if isinstance(final_reply, str) and final_reply.strip():
                        await _save_agent_fallback_message(
                            conversation_id=str(conv.id),
                            channel=channel,
                            content=final_reply.strip(),
                            customer_email=customer.email,
                            customer_phone=customer.phone_number,
                        )
                    else:
                        logger.warning(
                            "Agent returned no final output and no agent message was saved: conversation_id=%s",
                            conv.id,
                        )

                logger.info(
                    "Agent completed successfully: conversation_id=%s",
                    conv.id,
                )
                return True

        except RateLimitError as err:
            retry_seconds = _extract_retry_seconds(err)
            wait_text = (
                f" Please try again in about {retry_seconds} seconds."
                if retry_seconds is not None
                else " Please try again shortly."
            )

            logger.warning(
                "Model quota exceeded for channel=%s. Saving fallback response.",
                channel,
                exc_info=True,
            )

            try:
                await _save_agent_fallback_message(
                    conversation_id=str(conv.id),
                    channel=channel,
                    content=(
                        "We received your request, but our AI assistant is temporarily rate-limited."
                        f"{wait_text}"
                    ),
                    customer_email=customer.email,
                    customer_phone=customer.phone_number,
                )
            except Exception:
                logger.error("Failed to persist fallback rate-limit message", exc_info=True)

            return True

        except DBAPIError as err:
            if attempt == 0 and "connection was closed" in str(err).lower():
                logger.warning(
                    "Transient DB disconnect while processing message. Retrying once.",
                    exc_info=True,
                )
                continue

            logger.error(
                "Agent processing failed for message from channel=%s: %s",
                channel,
                err,
                exc_info=True,
            )
            return False

        except Exception as err:
            logger.error(
                "Agent processing failed for message from channel=%s: %s",
                channel,
                err,
                exc_info=True,
            )
            return False

    return False


def run_consumer_loop(consumer: Consumer, topics: list[str]):
    """Main Kafka consumer loop.
    
    Subscribes to topics and continuously processes incoming messages.
    On error: logs exception but continues consuming (offset not committed).
    On KeyboardInterrupt: gracefully shuts down.
    
    Args:
        consumer: Kafka consumer instance
        topics: List of topics to subscribe to (e.g., ['fte.inbound'])
    """
    consumer.subscribe(topics)
    logger.info("Kafka consumer subscribed to topics: %s", topics)
    
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            
            # Check for Kafka partition EOF (expected during normal operation)
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug("Reached end of partition")
                    continue
                raise KafkaException(msg.error())

            # Parse message
            try:
                data = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as err:
                logger.error("Failed to parse message JSON: %s", err)
                consumer.commit(message=msg, asynchronous=False)
                continue

            # Process message in async context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                handled = loop.run_until_complete(process_message(data))
                if handled:
                    consumer.commit(message=msg, asynchronous=False)
                    logger.debug("Message handled successfully, offset committed")
                else:
                    logger.error("Message not handled; offset NOT committed")
            
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down")
                consumer.close()
                raise
            
            except Exception as err:
                logger.error(
                    "Message loop failed unexpectedly (offset NOT committed): %s",
                    err,
                    exc_info=True,
                )
                # Offset NOT committed - message will be reprocessed on next run

    except KeyboardInterrupt:
        logger.info("Consumer shutting down gracefully")
        consumer.close()
    
    except Exception as err:
        logger.critical("Kafka consumer crashed: %s", err, exc_info=True)
        consumer.close()
        raise
        logger.info("Consumer shutting down.")
    finally:
        consumer.close()


if __name__ == "__main__":
    settings = get_settings()
    consumer = create_consumer()
    run_consumer_loop(consumer, [settings.kafka_intake_topic])
