# OpenAI Agents SDK - ChatCompletion Configuration Review

## Document Source
- **Official Docs:** https://openai.github.io/openai-agents-python
- **Key Pages Reviewed:**
  - https://openai.github.io/openai-agents-python/models/
  - https://openai.github.io/openai-agents-python/ref/models/openai_chatcompletions/

---

## 🎯 Key Findings from OpenAI Agents SDK Documentation

### 1. **Three Ways to Initialize OpenAI-Compatible Models**

The SDK supports multiple initialization patterns for Chat Completions model:

```python
# Option A: Simple string model name (uses default OpenAI provider)
agent = Agent(name="Assistant", model="gpt-4.1")

# Option B: Explicit OpenAIChatCompletionsModel with client
agent = Agent(
    name="Assistant",
    model=OpenAIChatCompletionsModel(
        model="gpt-4.1",
        openai_client=AsyncOpenAI()
    )
)

# Option C: Non-OpenAI provider (Gemini)
from agents import AsyncOpenAI, OpenAIChatCompletionsModel
client = AsyncOpenAI(
    api_key="your-gemini-key",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
model = OpenAIChatCompletionsModel(model="gemini-2.5-flash", openai_client=client)
```

---

### 2. **Critical Issue: Tracing with Non-OpenAI Providers**

**From the Official Docs:**
> "In cases where you do not have an API key from `platform.openai.com`, we recommend disabling tracing via `set_tracing_disabled()`, or setting up a [different tracing processor](https://openai.github.io/openai-agents-python/tracing/)."

**Why This Matters:**
When using Gemini API key with the OpenAI Agents SDK:
- The SDK tries to upload traces to OpenAI servers
- The Gemini API key is NOT valid for OpenAI's authentication
- This causes: `401 Unauthorized` in tracing, eventually leading to `400 Bad Request` in agent execution

**Error Example (What We Were Getting):**
```
WARNING:openai.agents:OPENAI_API_KEY is not set, skipping trace export
ERROR:openai.agents:Tracing client error 401
openai.BadRequestError: Error code: 400 - Missing or invalid Authorization header
```

---

### 3. **Proper Initialization for Gemini**

**Correct Pattern per SDK Docs:**

```python
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled

# For non-OpenAI providers (like Gemini), disable tracing
set_tracing_disabled(disabled=True)

# Create AsyncOpenAI client pointing to Gemini endpoint
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY not set")

client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Wrap in OpenAIChatCompletionsModel
model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=client
)

# Create agent with model
agent = Agent(
    name="MyAgent",
    model=model,
    instructions="You are helpful"
)
```

**Key Points:**
- ✅ Import `AsyncOpenAI` from `agents` package (not `openai`)
- ✅ Call `set_tracing_disabled(disabled=True)` FIRST
- ✅ Create `AsyncOpenAI` client with `api_key` and `base_url`
- ✅ Wrap in `OpenAIChatCompletionsModel`
- ✅ Pass model to `Agent` constructor

---

### 4. **AsyncOpenAI class - SDK vs OpenAI Package**

**Important Distinction:**

| Import | Package | Use Case |
|--------|---------|----------|
| `from agents import AsyncOpenAI` | openai-agents-sdk | ✅ Use this for Agents SDK |
| `from openai import AsyncOpenAI` | openai-python | Raw OpenAI API calls (not agents) |

The `agents` package re-exports `AsyncOpenAI` for convenience, ensuring compatibility with the SDK.

---

### 5. **OpenAIChatCompletionsModel Constructor**

From the official docs reference:

```python
class OpenAIChatCompletionsModel:
    def __init__(
        self,
        model: str,                                    # Model name (e.g., "gpt-4.1")
        openai_client: AsyncOpenAI | None = None,    # AsyncOpenAI client instance
        model_settings: ModelSettings | None = None,  # Optional: temperature, etc.
    ):
        pass
```

**Parameters:**
- `model` ✅ REQUIRED - Model identifier (for Gemini: "gemini-2.5-flash")
- `openai_client` ✅ REQUIRED - AsyncOpenAI instance with proper keys and base_url
- `model_settings` ⚠️ OPTIONAL - Temperature, timeout, extra_args, etc.

---

### 6. **Recommended Alternative: Set Default OpenAI Client**

For **simpler initialization** if using the same provider everywhere:

```python
from agents import set_default_openai_client, AsyncOpenAI, Agent

# One-time setup
gemini_api_key = os.getenv("GEMINI_API_KEY")
client = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
set_default_openai_client(client)

# Now agents use this client by default when model is a string
agent = Agent(name="MyAgent", model="gemini-2.5-flash")  # Works!
```

**Doc Reference:**
> "set_default_openai_client is useful in cases where you want to globally use an instance of AsyncOpenAI as the LLM client. This is for cases where the LLM provider has an OpenAI compatible API endpoint, and you can set the base_url and api_key."

---

### 7. **Tracing Configuration Options**

For non-OpenAI providers, you have three choices from the SDK docs:

**Option A: Disable Tracing (Simplest)**
```python
set_tracing_disabled(True)
```

**Option B: Use Separate OpenAI Key for Tracing**
```python
set_tracing_export_api_key("sk-...")  # OpenAI API key for trace uploading only
```

**Option C: Custom Tracing Processor**
```python
from agents import set_tracing_processor
# Implement custom processor that doesn't post to OpenAI
set_tracing_processor(my_custom_processor)
```

---

### 8. **Error: "Missing or invalid Authorization header"**

**Cause Chain:**
1. Gemini API key is set in environment
2. SDK initializes but tracing fails (Gemini key ≠ OpenAI key)
3. Traces are not exported (but processing continues)
4. When agent calls LLM, the client has correct base_url but...
5. If tracing still tries to interfere or client is misconfigured → 400 error

**Prevention:**
✅ Disable tracing early with `set_tracing_disabled(True)`
✅ Validate API key before client creation
✅ Use correct base_url for Gemini endpoint
✅ Import `AsyncOpenAI` from `agents` package

---

### 9. **Mixing OpenAI and Gemini Agents**

If you need both OpenAI and Gemini in same workflow:

```python
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel

# OpenAI agent (uses default tracing)
openai_agent = Agent(
    name="OpenAI Agent",
    model="gpt-4.1"
)

# Gemini agent (explicit model)
gemini_client = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
gemini_model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=gemini_client
)
gemini_agent = Agent(
    name="Gemini Agent",
    model=gemini_model
)

# Use in same run - they work independently
result = await Runner.run(openai_agent, "Hello")
result = await Runner.run(gemini_agent, "Hello")
```

---

### 10. **Configuration Best Practices**

From the official docs, for non-OpenAI providers:

✅ **DO:**
- Validate API key exists before client creation
- Disable tracing for non-platform.openai.com keys
- Use explicit `OpenAIChatCompletionsModel` wrapper
- Set base_url matching provider's API endpoint
- Handle errors gracefully with try/except

❌ **DON'T:**
- Set `os.environ["OPENAI_API_KEY"]` to non-OpenAI key (confuses SDK)
- Try to use Gemini key directly with OpenAI's Auth system
- Mix AsyncOpenAI imports from different packages
- Forget `set_tracing_disabled(True)` for non-OpenAI providers

---

## 📋 Implementation Checklist

For proper Gemini integration with OpenAI Agents SDK:

- [ ] Import `AsyncOpenAI` from `agents` package (not `openai`)
- [ ] Import `set_tracing_disabled` from `agents`
- [ ] Load and validate GEMINI_API_KEY from environment
- [ ] Call `set_tracing_disabled(disabled=True)` before any agent initialization
- [ ] Create `AsyncOpenAI` client with:
  - `api_key=gemini_api_key`
  - `base_url="https://generativelanguage.googleapis.com/v1beta/openai/"`
- [ ] Wrap client in `OpenAIChatCompletionsModel`:
  - `model="gemini-2.5-flash"`
  - `openai_client=client`
- [ ] Pass model to `Agent` constructor
- [ ] Add comprehensive logging at each step
- [ ] Document the configuration in code comments

---

## 🔗 Related Documentation Links

- **Models Configuration:** https://openai.github.io/openai-agents-python/models/
- **Non-OpenAI Providers:** https://openai.github.io/openai-agents-python/models/#non-openai-models
- **Troubleshooting:** https://openai.github.io/openai-agents-python/models/#troubleshooting-non-openai-providers
- **OpenAI ChatCompletions Model Ref:** https://openai.github.io/openai-agents-python/ref/models/openai_chatcompletions/
- **Tracing Documentation:** https://openai.github.io/openai-agents-python/tracing/

---

**Document Created:** April 9, 2026
**SDK Version Referenced:** v0.13.6 (latest available)
**Status:** ✅ Ready for Implementation
