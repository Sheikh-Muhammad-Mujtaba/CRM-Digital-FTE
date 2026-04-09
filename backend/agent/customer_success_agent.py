import logging

from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled

from agent.prompts import build_system_prompt
from agent.tools import (
    create_ticket,
    escalate_to_human,
    get_customer_history,
    search_knowledge_base,
    send_response,
)
from settings import get_settings

logger = logging.getLogger(__name__)

# ============================================================================
# GEMINI API CONFIGURATION FOR OPENAI AGENTS SDK
# ============================================================================
# Per https://openai.github.io/openai-agents-python/models/#non-openai-models:
#
# For non-OpenAI providers like Gemini, the SDK requires:
# 1. Disable tracing (Gemini key won't work with OpenAI tracing servers)
# 2. Create AsyncOpenAI client with base_url pointing to Gemini endpoint
# 3. Wrap in OpenAIChatCompletionsModel
# ============================================================================

# Step 1: Load and validate API key
gemini_api_key = get_settings().gemini_api_key

if not gemini_api_key:
    raise ValueError(
        "GEMINI_API_KEY environment variable is not set.\n"
        "\n"
        "Get a free API key:\n"
        "  1. Visit: https://aistudio.google.com/app/apikeys\n"
        "  2. Click: 'Create API Key in new project'\n"
        "  3. Copy the key and add to backend/.env\n"
    )

# Step 2: Disable tracing for non-OpenAI providers
# This prevents 401/400 errors when SDK tries to upload traces
# See: https://openai.github.io/openai-agents-python/models/#tracing-client-error-401
set_tracing_disabled(disabled=True)
logger.info("Tracing disabled for Gemini (non-OpenAI provider)")

# Step 3: Create AsyncOpenAI client with Gemini endpoint
# Import AsyncOpenAI from agents package (not openai client)
# See: https://openai.github.io/openai-agents-python/models/#ways-to-integrate-non-openai-providers
client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
logger.info("Initialized AsyncOpenAI client for Gemini")

# Step 4: Wrap in OpenAIChatCompletionsModel
# This implements the Model interface expected by the Agents SDK
model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=client
)
logger.info("Initialized OpenAIChatCompletionsModel wrapping Gemini")

crm_agent = Agent(
    name="CustomerSuccessFTE",
    model=model,
    instructions=build_system_prompt(),
    tools=[
        search_knowledge_base,
        get_customer_history,
        create_ticket,
        escalate_to_human,
        send_response,
    ],
)
