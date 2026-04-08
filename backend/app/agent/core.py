import json
import os
import uuid
import openai
from dotenv import load_dotenv

# Load environment variables before any module-level initializations
load_dotenv()

from agents import Agent, OpenAIChatCompletionsModel, function_tool
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.ticket import Ticket
from app.outbound.business import business_identity_block
from app.outbound.dispatch import dispatch_channel_reply

client = openai.AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY", ""),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

Model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=client,
)


class SearchQueryArgs(BaseModel):
    query: str = Field(description="The user's direct support inquiry or question")


class CreateTicketArgs(BaseModel):
    title: str = Field(description="A short one-line summary of the issue")
    description: str = Field(description="Detailed description and context")
    priority: str = Field(
        default="medium", description="Priority: low, medium, or high"
    )


class EscalateArgs(BaseModel):
    reason: str = Field(description="Why human intervention is required")


class ResponseArgs(BaseModel):
    response_text: str = Field(description="Final message to send to the customer")


@function_tool
async def search_knowledge_base(ctx, params: SearchQueryArgs) -> str:
    """Search product documentation (pgvector cosine similarity). Run after loading customer history."""
    try:
        from google import genai

        genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        emb_res = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=params.query,
        )
        query_vector = emb_res.embeddings[0].values

        from app.models.knowledge import KnowledgeBase

        stmt = (
            select(KnowledgeBase.title, KnowledgeBase.content)
            .order_by(KnowledgeBase.embedding.cosine_distance(query_vector))
            .limit(5)
        )
        result = await ctx.context.session.execute(stmt)
        articles = result.all()

        if not articles:
            return "No specific articles found matching the query."

        return "\n\n".join(
            [f"Title: {row.title}\nContent: {row.content}" for row in articles]
        )
    except Exception as e:
        return f"Knowledge search failed ({e!s}). Answer conservatively and offer escalation if unsure."


@function_tool
async def get_customer_history(ctx) -> str:
    """Mandatory: load past tickets for this customer to avoid duplicate work and align with prior resolutions."""
    stmt = (
        select(Ticket)
        .where(Ticket.customer_id == uuid.UUID(ctx.context.customer_id))
        .order_by(Ticket.created_at.desc())
        .limit(20)
    )
    result = await ctx.context.session.execute(stmt)
    tickets = result.scalars().all()
    rows = [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
        }
        for t in tickets
    ]
    return json.dumps(rows)


@function_tool
async def create_ticket(ctx, params: CreateTicketArgs) -> str:
    """Create a CRM support ticket; required for every conversation before sending a final reply."""
    new_ticket = Ticket(
        customer_id=uuid.UUID(ctx.context.customer_id),
        conversation_id=uuid.UUID(ctx.context.conversation_id),
        title=params.title,
        description=params.description,
        priority=params.priority,
        status="open",
    )
    ctx.context.session.add(new_ticket)
    await ctx.context.session.commit()
    return f"Ticket created. ID: {new_ticket.id}"


@function_tool
async def escalate_to_human(ctx, params: EscalateArgs) -> str:
    """Escalate to human CS; updates conversation state. For billing/refunds/legal demands, also create_ticket in the same turn."""
    conv_id = uuid.UUID(ctx.context.conversation_id)
    stmt = select(Conversation).where(Conversation.id == conv_id)
    res = await ctx.context.session.execute(stmt)
    conv = res.scalar_one_or_none()
    if conv:
        conv.status = "escalated"
    note = Message(
        conversation_id=conv_id,
        sender_type="system",
        content=f"ESCALATED: {params.reason}",
        channel=ctx.context.channel,
    )
    ctx.context.session.add(note)
    await ctx.context.session.commit()
    return f"Escalation recorded: {params.reason}"


@function_tool
async def send_response(ctx, params: ResponseArgs) -> str:
    """Save the reply and deliver it on the active channel (WhatsApp via Twilio, web/email via Gmail API)."""
    msg = Message(
        conversation_id=uuid.UUID(ctx.context.conversation_id),
        sender_type="agent",
        content=params.response_text,
        channel=ctx.context.channel,
    )
    ctx.context.session.add(msg)
    await ctx.context.session.commit()
    outbound = await dispatch_channel_reply(
        channel=ctx.context.channel,
        customer_email=ctx.context.customer_email,
        customer_phone=ctx.context.customer_phone,
        response_text=params.response_text,
    )
    return f"Response saved. Outbound: {outbound}"


crm_agent = Agent(
    name="CustomerSuccessFTE",
    model=Model,
    instructions=f"""
{business_identity_block()}

You are the Digital Customer Success / technical support FTE for this company. Follow tools in this order for every inbound message:
1) get_customer_history — always first.
2) search_knowledge_base — before stating service capabilities or technical facts.
3) create_ticket — once per conversation with a clear title and description (this thread is new, so create one ticket before replying).
4) send_response — final text only after steps 1–3. This step delivers the message to the customer on their channel.

Channel behavior:
- email: professional, empathetic, full sentences, clear sections if needed, signature line for the business.
- web: semi-formal and clear; the customer receives this text by email at the address they provided on the form.
- whatsapp: concise, conversational, prefer under ~400 characters when possible; plain text, no markdown tables.

Escalate (escalate_to_human) when: pricing negotiations, refunds/chargebacks, legal/compliance, data deletion demands,
abuse/safety, or you cannot answer after searching the knowledge base. For those cases, still create_ticket first,
then escalate_to_human, then send_response acknowledging escalation.

Never invent SLAs, certifications, or vendor partnerships; only use the knowledge base and customer history. Do not discuss competitors.
""",
    tools=[
        search_knowledge_base,
        get_customer_history,
        create_ticket,
        escalate_to_human,
        send_response,
    ],
)
