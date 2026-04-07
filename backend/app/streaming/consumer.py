import os
import json
import asyncio
from dotenv import load_dotenv
from confluent_kafka import Consumer, KafkaError, KafkaException

load_dotenv()

from app.core.database import AsyncSessionLocal
from app.agent.core import crm_agent
from app.agent.deps import AgentDependencies
from sqlalchemy import select
from app.models.customer import Customer
from app.models.conversation import Conversation
from app.models.message import Message
import uuid

def create_consumer():
    conf = {
        'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092'),
        'group.id': 'crm-agent-group',
        'auto.offset.reset': 'earliest'
    }
    return Consumer(conf)

async def process_message(msg_data):
    print(f"Processing event from {msg_data.get('channel')}: {msg_data.get('message')}")
    
    async with AsyncSessionLocal() as session:
        # Simple lookup or create based on email (for web)
        email = msg_data.get('customer_email')
        stmt = select(Customer).where(Customer.email == email)
        result = await session.execute(stmt)
        customer = result.scalars().first()
        
        if not customer:
            customer = Customer(
                name=msg_data.get('customer_name', 'Guest'),
                email=email,
                phone_number=msg_data.get('customer_phone')
            )
            session.add(customer)
            await session.commit()
            await session.refresh(customer)
            
        # Create a basic conversation to map this run
        conv = Conversation(customer_id=customer.id)
        session.add(conv)
        
        # Save user message
        user_msg = Message(
            conversation_id=conv.id,
            sender_type="user",
            content=msg_data.get('message'),
            channel=msg_data.get('channel')
        )
        session.add(user_msg)
        await session.commit()
        await session.refresh(conv)

        deps = AgentDependencies(
            session=session,
            customer_id=str(customer.id),
            channel=msg_data.get('channel'),
            conversation_id=str(conv.id)
        )
        
        try:
            result = await crm_agent.run(
                msg_data.get('message'),
                deps=deps
            )
            print(f"[{msg_data.get('channel')}] Agent output processed successfully.")
        except Exception as e:
            print(f"Agent error: {e}")

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
                else:
                    raise KafkaException(msg.error())
            
            data = json.loads(msg.value().decode('utf-8'))
            
            # Since process is async, run in loop
            # using asyncio.run generates error if loop already running, we can just use simple event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.run_until_complete(process_message(data))

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    c = create_consumer()
    print("Starting Kafka Consumer worker...")
    run_consumer_loop(c, ["crm_intake"])
