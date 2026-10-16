import os
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

from app.core.logging import logger

load_dotenv(
    os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(__file__)
            )
        ),
        ".env",
    ),
    override=True,
)

# ============================================================
# TEXT LLM CONFIGURATION
# ============================================================

AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").strip().lower()

# ─── Groq ───
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ─── OpenAI ───
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ─── Gemini ───
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ─── OpenRouter ───
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "deepseek/deepseek-r1:free",
)

# ─── Cerebras ───
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.3-70b")

# ─── Pollinations (no key) ───
POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "openai")


# ============================================================
# CLIENT INITIALIZATION
# ============================================================

groq_client = (
    Groq(api_key=GROQ_API_KEY)
    if GROQ_API_KEY
    else None
)

openai_client = (
    OpenAI(api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY
    else None
)

gemini_client = (
    OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=GEMINI_API_KEY,
    )
    if GEMINI_API_KEY
    else None
)

openrouter_client = (
    OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    if OPENROUTER_API_KEY
    else None
)

cerebras_client = (
    OpenAI(
        base_url="https://api.cerebras.ai/v1",
        api_key=CEREBRAS_API_KEY,
    )
    if CEREBRAS_API_KEY
    else None
)

pollinations_client = OpenAI(
    base_url="https://text.pollinations.ai/openai",
    api_key="dummy",   # no key required
)


# ============================================================
# COMMON LLM FUNCTION — provider-agnostic
# ============================================================

def _call_openai_compatible(
    client: OpenAI,
    model: str,
    messages: list,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> str:
    """Generic OpenAI-compatible chat call."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)

    if not response.choices:
        raise RuntimeError(f"{model}: returned no choices")

    content = response.choices[0].message.content

    if content is None:
        raise RuntimeError(f"{model}: returned no content")

    return content.strip()


def generate_llm_response(
    messages: list,
    max_tokens: int = 500,
    temperature: float = 0.2,
    json_mode: bool = False,
):
    """
    Universal LLM call.
    Routes to the configured provider — works with any API key.
    """

    # ─── GROQ ───
    if AI_PROVIDER == "groq":
        if groq_client is None:
            raise RuntimeError("GROQ_API_KEY is not configured")

        logger.info("Using Groq model: %s", GROQ_MODEL)

        kwargs = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = groq_client.chat.completions.create(**kwargs)

        if not response.choices:
            raise RuntimeError("Groq returned no choices")

        content = response.choices[0].message.content

        if content is None:
            raise RuntimeError("Groq returned no content")

        return content.strip()

    # ─── OPENAI ───
    if AI_PROVIDER == "openai":
        if openai_client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        logger.info("Using OpenAI model: %s", OPENAI_MODEL)

        return _call_openai_compatible(
            openai_client,
            OPENAI_MODEL,
            messages,
            max_tokens,
            temperature,
            json_mode,
        )

    # ─── GEMINI (OpenAI-compatible endpoint) ───
    if AI_PROVIDER == "gemini":
        if gemini_client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        logger.info("Using Gemini model: %s", GEMINI_MODEL)

        return _call_openai_compatible(
            gemini_client,
            GEMINI_MODEL,
            messages,
            max_tokens,
            temperature,
            json_mode,
        )

    # ─── OPENROUTER (free models) ───
    if AI_PROVIDER == "openrouter":
        if openrouter_client is None:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        logger.info("Using OpenRouter model: %s", OPENROUTER_MODEL)

        return _call_openai_compatible(
            openrouter_client,
            OPENROUTER_MODEL,
            messages,
            max_tokens,
            temperature,
            json_mode,
        )

    # ─── CEREBRAS (free tier) ───
    if AI_PROVIDER == "cerebras":
        if cerebras_client is None:
            raise RuntimeError("CEREBRAS_API_KEY is not configured")

        logger.info("Using Cerebras model: %s", CEREBRAS_MODEL)

        return _call_openai_compatible(
            cerebras_client,
            CEREBRAS_MODEL,
            messages,
            max_tokens,
            temperature,
            json_mode,
        )

    # ─── POLLINATIONS (no key) ───
    if AI_PROVIDER == "pollinations":
        logger.info("Using Pollinations model: %s", POLLINATIONS_MODEL)

        return _call_openai_compatible(
            pollinations_client,
            POLLINATIONS_MODEL,
            messages,
            max_tokens,
            temperature,
            json_mode,
        )

    raise ValueError(
        f"Unsupported AI_PROVIDER: {AI_PROVIDER}. "
        "Use 'groq', 'openai', 'gemini', 'openrouter', "
        "'cerebras', or 'pollinations'."
    )