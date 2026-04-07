import os
import json
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

conf = {
    'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
}

producer = Producer(conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def publish_event(topic: str, event_data: dict):
    producer.produce(
        topic, 
        key=str(event_data.get('customer_id', 'none')), 
        value=json.dumps(event_data).encode('utf-8'),
        callback=delivery_report
    )
    producer.poll(0)
    # Ensure delivery in a robust app, but for high throughput poll(0) is fine
