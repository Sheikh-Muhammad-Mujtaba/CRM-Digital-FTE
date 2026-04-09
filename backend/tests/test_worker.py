import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")

from workers.kafka import create_consumer


def test_consumer_factory():
    consumer = create_consumer()
    assert consumer is not None
