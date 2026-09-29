import os
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

from app.core.logging import logger
# load_dotenv(override=True)


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
# LLM CONFIGURATION
# ============================================================

AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").strip().lower()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna",
)


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


# ============================================================
# COMMON LLM FUNCTION
# ============================================================

def generate_llm_response(
    messages: list,
    max_tokens: int = 500,
    temperature: float = 0.2,
    json_mode: bool = False,
):
    if AI_PROVIDER == "groq":
        if groq_client is None:
            raise RuntimeError("GROQ_API_KEY is not configured")

        logger.info("Using Groq model: %s", GROQ_MODEL)

        request_kwargs = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            request_kwargs["response_format"] = {
                "type": "json_object"
            }

        response = groq_client.chat.completions.create(
            **request_kwargs
        )

        if not response.choices:
            raise RuntimeError("Groq returned no choices")

        content = response.choices[0].message.content

        if content is None:
            raise RuntimeError("Groq returned no message content")

        return content.strip()

    if AI_PROVIDER == "openai":
        if openai_client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        logger.info("Using OpenAI model: %s", OPENAI_MODEL)

        response = openai_client.responses.create(
            model=OPENAI_MODEL,
            input=messages,
            max_output_tokens=max_tokens,
        )

        if not response.output_text:
            raise RuntimeError("OpenAI returned an empty response")

        return response.output_text.strip()

    raise ValueError(
        f"Unsupported AI_PROVIDER: {AI_PROVIDER}. "
        "Use 'groq' or 'openai'."
    )