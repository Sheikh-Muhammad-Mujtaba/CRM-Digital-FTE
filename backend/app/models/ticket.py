import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Ticket(Base):
    __tablename__ = 'tickets'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('customers.id'), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('conversations.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open") # open, in_progress, resolved
    priority: Mapped[str] = mapped_column(String(50), default="medium") # low, medium, high
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="tickets")
    conversation = relationship("Conversation", back_populates="tickets")
