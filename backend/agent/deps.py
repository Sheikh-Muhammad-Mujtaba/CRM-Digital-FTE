from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AgentDependencies:
    session: AsyncSession
    customer_id: str
    channel: str
    conversation_id: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
