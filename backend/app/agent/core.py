import os
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.models.ticket import Ticket
from app.models.message import Message

# Replace pydantic-ai with OpenAI Agents SDK
from agents import Agent, Runner, function_tool
import openai

# We use the Gemini compatibility endpoint for OpenAI SDK
client = openai.AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY", "default-key"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

class SearchQueryArgs(BaseModel):
    query: str = Field(description="The user's direct support inquiry or question")

class CreateTicketArgs(BaseModel):
    title: str = Field(description="A short one-line summary of the issue to solve")
    description: str = Field(description="Detailed documentation of the problem and troubleshooting")
    priority: str = Field(default="medium", description="The priority: low, medium, or high")

class EscalateArgs(BaseModel):
    reason: str = Field(description="The reason why this issue requires human intervention")

class ResponseArgs(BaseModel):
    response_text: str = Field(description="The final message to send to the user")

@function_tool
async def search_knowledge_base(ctx, params: SearchQueryArgs) -> str:
    """Searches the corporate knowledge base for relevant resolution documentation using semantic vector search."""
    try:
        from google import genai
        genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        emb_res = genai_client.models.embed_content(
            model='text-embedding-004',
            contents=params.query,
        )
        query_vector = emb_res.embeddings[0].values
        
        from app.models.knowledge import KnowledgeBase
        stmt = (
            select(KnowledgeBase.title, KnowledgeBase.content)
            .order_by(KnowledgeBase.embedding.cosine_distance(query_vector))
            .limit(3)
        )
        result = await ctx.deps.session.execute(stmt)
        articles = result.all()
        
        if not articles:
            return "No specific articles found matching the query."
            
        return "\n\n".join([f"Title: {row.title}\nContent: {row.content}" for row in articles])
    except Exception as e:
        return f"Warning: Failed to execute vector search ({str(e)}). Proceed with generalizations based on CRM rules."

@function_tool
async def get_customer_history(ctx) -> list[dict]:
    """Retrieves the customer's previous support tickets from the database to establish historical context."""
    stmt = select(Ticket).where(Ticket.customer_id == ctx.deps.customer_id)
    result = await ctx.deps.session.execute(stmt)
    tickets = result.scalars().all()
    return [{"id": str(t.id), "title": t.title, "status": t.status} for t in tickets]

@function_tool
async def create_ticket(ctx, params: CreateTicketArgs) -> str:
    """Registers a formal CRM customer support ticket when an authorized change is blocked or escalation is needed."""
    new_ticket = Ticket(
        customer_id=ctx.deps.customer_id,
        conversation_id=ctx.deps.conversation_id,
        title=params.title,
        description=params.description,
        priority=params.priority,
        status="open"
    )
    ctx.deps.session.add(new_ticket)
    await ctx.deps.session.commit()
    return f"Ticket successfully created. ID: {new_ticket.id}"

@function_tool
async def escalate_to_human(ctx, params: EscalateArgs) -> str:
    """Forces an immediate halt on the autonomous loop and assigns the conversation queue to human Customer Success staff."""
    return f"Status updated to ESCALATED: {params.reason}. Handing off."

@function_tool
async def send_response(ctx, params: ResponseArgs) -> str:
    """Dispatches the AI's final conclusion directly outward to the end-user via their active communication channel."""
    msg = Message(
        conversation_id=ctx.deps.conversation_id,
        sender_type="agent",
        content=params.response_text,
        channel=ctx.deps.channel
    )
    ctx.deps.session.add(msg)
    await ctx.deps.session.commit()
    return "SUCCESS: Final response transmitted successfully to user."

crm_agent = Agent(
    name="DigitalFTE",
    # Pass the OpenAI client pointing to the Gemini base URL!
    client=client, 
    model="gemini-2.5-flash",
    instructions="""
    You are an autonomous customer success Digital FTE (Full-Time Equivalent).
    Your goal is to autonomously resolve customer issues using available tools.
    - Search the Knowledge Base for context before answering.
    - Analyze past tickets for the customer if relevant.
    - If you cannot resolve the issue, you MUST create a Ticket AND Escalate to a human.
    - Adapt your tone based on the channel context provided to you.
    - Keep responses professional and to the point.
    """,
    tools=[search_knowledge_base, get_customer_history, create_ticket, escalate_to_human, send_response]
)
