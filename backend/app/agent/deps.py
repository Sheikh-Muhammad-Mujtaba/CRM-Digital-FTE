from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class AgentDependencies:
    session: AsyncSession
    customer_id: str
    channel: str
    conversation_id: str
