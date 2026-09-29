import asyncio
import httpx
import os
import re
import re as _re
import feedparser
import json
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
import cloudinary
import cloudinary.uploader
from app.db.database import execute_query
from app.core.logging import logger
from app.ai.llm import generate_llm_response, AI_PROVIDER

# ============================================================
# CONFIGURATION
# ============================================================

CALENDARIFIC_API_KEY = os.getenv("CALENDARIFIC_API_KEY")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")


# ============================================================
# CLOUDINARY
# ============================================================

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


POLLINATIONS_IMAGE_URL = "https://gen.pollinations.ai/image"


# ============================================================
# HOLIDAYS
# ============================================================

async def fetch_holidays(country_code: str, year: int = None) -> list:

    if not year:
        year = datetime.now().year

    cached = execute_query(
        """
        SELECT id
        FROM events_cache
        WHERE country_code = %s
        AND fetched_at::date = CURRENT_DATE
        LIMIT 1
        """,
        (country_code,),
        fetch="one"
    )

    if cached:
        return execute_query(
            """
            SELECT *
            FROM events_cache
            WHERE country_code = %s
            AND event_date >= CURRENT_DATE
            AND event_date <= CURRENT_DATE + INTERVAL '30 days'
            ORDER BY event_date ASC
            """,
            (country_code,),
            fetch="all"
        ) or []

    try:

        async with httpx.AsyncClient(timeout=15.0) as client:

            resp = await client.get(
                "https://calendarific.com/api/v2/holidays",
                params={
                    "api_key": CALENDARIFIC_API_KEY,
                    "country": country_code,
                    "year": year
                }
            )

            data = resp.json()
            holidays = data.get("response", {}).get("holidays", [])

            if not holidays:
                logger.warning(
                    "No holidays returned for %s",
                    country_code
                )
                return []

            execute_query(
                "DELETE FROM events_cache WHERE country_code = %s",
                (country_code,)
            )

            for h in holidays:

                event_date = h.get("date", {}).get("iso", "")[:10]

                if not event_date:
                    continue

                event_type = h.get("type", ["general"])

                event_type = (
                    event_type[0]
                    if isinstance(event_type, list)
                    else event_type
                )

                execute_query(
                    """
                    INSERT INTO events_cache
                        (
                            country_code,
                            event_name,
                            event_date,
                            event_type,
                            raw_data
                        )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        country_code,
                        h.get("name"),
                        event_date,
                        event_type,
                        json.dumps(h)
                    )
                )

            logger.info(
                "%s holidays/festivals cached for %s",
                len(holidays),
                country_code
            )

    except Exception:
        logger.exception(
            "Calendarific fetch failed for %s",
            country_code
        )
        return []

    return execute_query(
        """
        SELECT *
        FROM events_cache
        WHERE country_code = %s
        AND event_date >= CURRENT_DATE
        AND event_date <= CURRENT_DATE + INTERVAL '30 days'
        ORDER BY event_date ASC
        """,
        (country_code,),
        fetch="all"
    ) or []


# ============================================================
# GOOGLE NEWS TRENDS
# ============================================================

def fetch_google_trends(country_code: str, industry: str) -> list:

    cached = execute_query(
        """
        SELECT id
        FROM trends_cache
        WHERE country_code = %s
        AND platform = 'google_news'
        AND fetched_at > NOW() - INTERVAL '6 hours'
        LIMIT 1
        """,
        (country_code,),
        fetch="one"
    )

    if cached:
        return execute_query(
            """
            SELECT *
            FROM trends_cache
            WHERE country_code = %s
            AND platform = 'google_news'
            AND fetched_at > NOW() - INTERVAL '6 hours'
            ORDER BY score DESC
            """,
            (country_code,),
            fetch="all"
        ) or []

    locale_map = {
        "IN": ("en-IN", "IN"),
        "US": ("en-US", "US"),
        "GB": ("en-GB", "GB"),
        "AU": ("en-AU", "AU"),
        "CA": ("en-CA", "CA"),
    }

    hl, gl = locale_map.get(
        country_code,
        ("en-IN", "IN")
    )

    rss_urls = [
        (
            f"https://news.google.com/rss?"
            f"hl={hl}&gl={gl}&ceid={gl}:en"
        ),
        (
            f"https://news.google.com/rss/search?"
            f"q={quote(industry.split(',')[0].strip())}"
            f"&hl={hl}&gl={gl}&ceid={gl}:en"
        ),
        (
            f"https://news.google.com/rss/search?"
            f"q=social+media+trends"
            f"&hl={hl}&gl={gl}&ceid={gl}:en"
        ),
    ]

    topics = []

    for url in rss_urls:

        try:

            feed = feedparser.parse(url)

            for entry in feed.entries[:5]:

                title = entry.get("title", "").strip()

                if title and title not in topics:
                    topics.append(title)

        except Exception:
            logger.exception(
                "RSS feed failed for Google News"
            )
            continue

    if not topics:

        logger.warning(
            "No Google News trends fetched for %s",
            country_code
        )

        return []

    execute_query(
        """
        DELETE FROM trends_cache
        WHERE country_code = %s
        AND platform = 'google_news'
        """,
        (country_code,)
    )

    for i, topic in enumerate(topics[:15]):

        execute_query(
            """
            INSERT INTO trends_cache
                (
                    country_code,
                    platform,
                    topic,
                    score
                )
            VALUES (%s, %s, %s, %s)
            """,
            (
                country_code,
                "google_news",
                topic,
                15 - i
            )
        )

    logger.info(
        "Google News trends fetched for %s",
        country_code
    )

    return execute_query(
        """
        SELECT *
        FROM trends_cache
        WHERE country_code = %s
        AND platform = 'google_news'
        ORDER BY score DESC
        """,
        (country_code,),
        fetch="all"
    ) or []


# ============================================================
# CONTENT FILTERING
# ============================================================

EXCLUDED_EVENT_TYPES = {
    "religious",
    "observance",
    "national",
}

BASE_EXCLUDED_KEYWORDS = [
    "christmas",
    "easter",
    "hanukkah",
    "passover",
    "good friday",
    "navratri",
    "puja",
    "church",
    "mosque",
    "temple",
    "holy",
    "saint",
    "prophet",
    "religious",
    "pilgrimage",
    "hajj",
    "yom kippur",

    "election",
    "president",
    "minister",
    "parliament",
    "senate",
    "congress",
    "political",
    "protest",
    "referendum",
    "coup",
    "rebellion",
    "uprising",
    "vote",
    "campaign",
    "party leader",
    "republic day",
    "independence day",
    "constitution day",

    "terrorist",
    "terrorism",
    "war",
    "attack",
    "shooting",
    "bombing",
    "terror",
    "assassination",
    "riot",
    "violence",
    "killed",
    "massacre",
    "conflict",
    "military strike",
]

INDUSTRY_EXTRA_KEYWORDS = {
    "tech": [
        "martyr",
        "war memorial",
        "armed forces",
        "military",
    ],
}


def _is_blocked(text: str, industry: str) -> bool:

    if not text:
        return False

    text_lower = text.lower()

    keywords = (
        BASE_EXCLUDED_KEYWORDS
        + INDUSTRY_EXTRA_KEYWORDS.get(
            (industry or "").lower(),
            []
        )
    )

    for kw in keywords:

        pattern = r"\b" + re.escape(kw) + r"\b"

        if re.search(pattern, text_lower):
            return True

    return False


def _prefilter_events(events: list, industry: str) -> list:

    safe = []

    for e in events or []:

        event_type = (
            e.get("event_type") or ""
        ).lower()

        if event_type in EXCLUDED_EVENT_TYPES:

            logger.info(
                "Excluded event by type: %s",
                e.get("event_name")
            )

            continue

        if _is_blocked(
            e.get("event_name", ""),
            industry
        ):

            logger.info(
                "Excluded event by keyword: %s",
                e.get("event_name")
            )

            continue

        safe.append(e)

    return safe


def _prefilter_trends(trends: list, industry: str) -> list:

    safe = []

    for t in trends or []:

        if _is_blocked(
            t.get("topic", ""),
            industry
        ):

            logger.info(
                "Excluded trend by keyword: %s",
                t.get("topic")
            )

            continue

        safe.append(t)

    return safe


def _postfilter_llm_output(
    result: dict,
    industry: str
) -> dict:

    clean_events = []

    for e in result.get(
        "relevant_events",
        []
    ):

        if (
            _is_blocked(
                e.get("event_name", ""),
                industry
            )
            or
            _is_blocked(
                e.get("angle", ""),
                industry
            )
        ):

            logger.info(
                "Post-filter dropped event: %s",
                e.get("event_name")
            )

            continue

        clean_events.append(e)

    clean_trends = []

    for t in result.get(
        "relevant_trends",
        []
    ):

        if (
            _is_blocked(
                t.get("topic", ""),
                industry
            )
            or
            _is_blocked(
                t.get("angle", ""),
                industry
            )
        ):

            logger.info(
                "Post-filter dropped trend: %s",
                t.get("topic")
            )

            continue

        clean_trends.append(t)

    return {
        "relevant_events": clean_events,
        "relevant_trends": clean_trends,
    }


# ============================================================
# LLM - RELEVANCE FILTER
# ============================================================

def filter_relevant_events(
    events: list,
    trends: list,
    profile: dict
) -> dict:

    industry = profile.get(
        "industry",
        ""
    )

    events = _prefilter_events(
        events,
        industry
    )

    trends = _prefilter_trends(
        trends,
        industry
    )

    if not events and not trends:

        return {
            "relevant_events": [],
            "relevant_trends": []
        }

    events_list = [
        (
            f"- {e['event_name']} "
            f"on {e['event_date']} "
            f"(type: {e['event_type']})"
        )
        for e in (events or [])
    ]

    trends_list = [
        f"- {t['topic']}"
        for t in (trends or [])[:10]
    ]

    prompt = f"""
You are a social media strategist.

User Profile:
- Persona  : {profile.get('persona')}
- Industry : {profile.get('industry')}
- Brand    : {profile.get('brand_name')}
- Tone     : {profile.get('tone')}
- Audience : {profile.get('audience')}

Upcoming events (next 30 days):
{chr(10).join(events_list) if events_list else "None"}

Currently trending topics:
{chr(10).join(trends_list) if trends_list else "None"}

STRICT CONTENT RULES
(apply to every event/trend you select AND to the angle you write):

- Do NOT select or reference anything religious.
- Do NOT select or reference anything political.
- Do NOT select or reference anything violent, tragic, or related to war,
  conflict, attacks, or death.
- If nothing qualifies, return empty lists.
- Do not force a selection.

Select maximum 3 events AND maximum 3 trends most relevant
for this user, respecting the rules above.

For each selected item, give a specific post angle.

Return ONLY valid JSON.
Do not return markdown.
Do not return code fences.

{{
  "relevant_events": [
    {{
      "event_name": "name",
      "event_date": "YYYY-MM-DD",
      "angle": "specific angle for this user's brand and audience"
    }}
  ],
  "relevant_trends": [
    {{
      "topic": "trend name",
      "angle": "specific angle for this user's brand and audience"
    }}
  ]
}}
"""

    try:
        raw = generate_llm_response(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=2000,
            temperature=0.2,
            json_mode=True,
        )

        raw = raw.strip()

        if raw.startswith("```json"):
            raw = raw[7:]

        if raw.startswith("```"):
            raw = raw[3:]

        if raw.endswith("```"):
            raw = raw[:-3]

        raw = raw.strip()
        logger.info("Raw Groq post response: %r", raw)


        result = json.loads(raw)

    except Exception:

        logger.exception(
            "%s relevance filter failed",
            AI_PROVIDER
        )

        return {
            "relevant_events": [],
            "relevant_trends": []
        }

    return _postfilter_llm_output(
        result,
        industry
    )


# ============================================================
# RAG
# ============================================================

def _normalize_text(text: str) -> str:

    return re.sub(
        r"[^a-z0-9\s]",
        " ",
        (text or "").lower()
    )


STOPWORDS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "how",
    "why",
    "should",
    "could",
    "would",
    "will",
    "can",
    "may",
    "might",
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "did",
    "does",
    "this",
    "that",
    "with",
    "from",
    "your",
    "our",
    "their",
    "his",
    "her",
    "its",
    "you",
    "they",
    "them",
    "some",
    "any",
    "all",
    "more",
    "also",
    "just",
    "about",
    "into",
    "than",
    "then",
    "now",
    "not",
    "but",
    "out",
    "give",
    "tell",
    "show",
    "get",
    "make",
    "use",
    "need",
    "want",
    "like",
    "help",
    "know",
    "see",
    "look",
    "think",
    "much",
    "many",
}


def _get_query_tokens(query: str) -> set:

    return {
        token
        for token in _normalize_text(query).split()
        if len(token) > 2
        and token not in STOPWORDS
    }


def _score_doc_text(
    text: str,
    query_tokens: set
) -> int:

    tokens = _normalize_text(text).split()

    return sum(
        1
        for t in tokens
        if t in query_tokens
    )


def _get_rag_documents(
    user_id: int
) -> list:

    docs = []

    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (user_id,),
        fetch="one"
    ) or {}

    if profile:

        docs.append(
            {
                "source": "Profile",
                "title": "User profile summary",
                "content": (
                    f"Persona: {profile.get('persona', '')}\n"
                    f"Industry: {profile.get('industry', '')}\n"
                    f"Brand: {profile.get('brand_name', '')}\n"
                    f"Tone: {profile.get('tone', '')}\n"
                    f"Audience: {profile.get('audience', '')}\n"
                    f"Country: {profile.get('country_code', '')}\n"
                    f"Language: {profile.get('language', '')}\n"
                    f"Posts per week: {profile.get('posts_per_week', '')}"
                )
            }
        )

    recent_posts = execute_query(
        """
        SELECT
            content_text,
            platforms,
            created_at
        FROM post_templates
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 8
        """,
        (user_id,),
        fetch="all"
    ) or []

    for post in recent_posts:

        docs.append(
            {
                "source": "Recent post",
                "title": post.get(
                    "created_at",
                    "Recent post"
                ),
                "content": (
                    f"Content: {post.get('content_text', '')}\n"
                    f"Platforms: "
                    f"{', '.join(post.get('platforms', []) or [])}"
                )
            }
        )

    country_code = (
        profile.get("country_code")
        if profile
        else None
    )

    if country_code:

        events = execute_query(
            """
            SELECT
                event_name,
                event_date,
                event_type
            FROM events_cache
            WHERE country_code = %s
            ORDER BY event_date ASC
            LIMIT 8
            """,
            (country_code,),
            fetch="all"
        ) or []

        for event in events:

            docs.append(
                {
                    "source": "Upcoming event",
                    "title": event.get(
                        "event_name",
                        "Event"
                    ),
                    "content": (
                        f"Event: "
                        f"{event.get('event_name', '')}\n"
                        f"Date: "
                        f"{event.get('event_date', '')}\n"
                        f"Type: "
                        f"{event.get('event_type', '')}"
                    )
                }
            )

        trends = execute_query(
            """
            SELECT topic
            FROM trends_cache
            WHERE country_code = %s
            ORDER BY score DESC
            LIMIT 8
            """,
            (country_code,),
            fetch="all"
        ) or []

        for trend in trends:

            docs.append(
                {
                    "source": "Trending topic",
                    "title": trend.get(
                        "topic",
                        "Trend"
                    ),
                    "content": (
                        f"Topic: "
                        f"{trend.get('topic', '')}"
                    )
                }
            )

    return docs


def retrieve_rag_documents(
    user_id: int,
    query: str,
    limit: int = 4
) -> list:

    docs = _get_rag_documents(user_id)

    query_tokens = _get_query_tokens(query)

    scored = [
        (
            _score_doc_text(
                doc["content"],
                query_tokens
            ),
            doc
        )
        for doc in docs
    ]

    scored.sort(
        key=lambda item: item[0],
        reverse=True
    )

    selected = [
        doc
        for score, doc in scored
        if score > 0
    ][:limit]

    return selected


def _get_chat_history(
    user_id: int,
    limit: int = 6
) -> list:

    rows = execute_query(
        """
        SELECT
            role,
            content
        FROM rag_chat_history
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, limit),
        fetch="all"
    ) or []

    return list(reversed(rows))


def _save_chat_turn(
    user_id: int,
    role: str,
    content: str
):

    execute_query(
        """
        INSERT INTO rag_chat_history
            (user_id, role, content)
        VALUES (%s, %s, %s)
        """,
        (
            user_id,
            role,
            content
        )
    )


# ============================================================
# LLM - RAG QUERY
# ============================================================


def answer_rag_query(user_id: int, query: str) -> dict:
    """
    Answer user questions using SocialDesk context when relevant,
    while still allowing general knowledge questions.

    RAG context is supplemental, not a hard restriction.
    """

    docs = retrieve_rag_documents(user_id, query, limit=5)

    sources = [
        f"{doc['source']} - {doc['title']}"
        for doc in docs
    ]

    context = "\n\n".join(
        f"Source: {doc['source']}\n{doc['content']}"
        for doc in docs
    )

    if not context:
        context = "No relevant SocialDesk context was found."

    history = _get_chat_history(user_id, limit=6)

    system_prompt = f"""
You are the AI assistant for SocialDesk.

You are a general-purpose helpful assistant with access to
optional SocialDesk user context.

IMPORTANT RULES:

1. Answer general knowledge questions normally using your
   knowledge.

2. Do NOT require the answer to exist in the SocialDesk context.

3. If the user's question is about their SocialDesk account,
   profile, brand, posts, trends, scheduled posts, audience,
   platforms, or other user-specific information, use the
   provided SocialDesk context whenever relevant.

4. If the SocialDesk context does not contain enough information
   for a user-specific question, clearly say that the information
   is not available rather than inventing user-specific facts.

5. For general questions, answer directly even when the
   SocialDesk context is unrelated.

6. Never say:
   "The answer is not specified in the provided context"
   merely because the context does not contain the answer.

7. Do not treat unrelated retrieved documents as relevant
   evidence.

8. Be concise, natural, and helpful.

9. If the user asks for an explanation, explain it clearly
   instead of only giving a short answer.

10. If the user asks a simple factual question, give the direct
    answer first.

SOCIALDESK CONTEXT:
{context}
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for turn in history:
        role = turn.get("role")

        if role not in {"user", "assistant"}:
            continue

        messages.append(
            {
                "role": role,
                "content": turn["content"],
            }
        )

    messages.append(
        {
            "role": "user",
            "content": query,
        }
    )

    try:

        answer = generate_llm_response(
            messages=messages,
            max_tokens=450,
            temperature=0.2,
        )

        _save_chat_turn(
            user_id,
            "user",
            query,
        )

        _save_chat_turn(
            user_id,
            "assistant",
            answer,
        )

        return {
            "answer": answer,
            "sources": sources,
        }

    except Exception:
        logger.exception(
            "%s RAG query failed",
            AI_PROVIDER
        )

        return {
            "answer": "Could not answer right now. Please try again.",
            "sources": sources,
        }
# ============================================================
# LLM - POST GENERATION
# ============================================================

def generate_post_content(
    profile: dict,
    trigger: dict,
    platform: str
 ) -> dict:

    platform_rules = {
        "linkedin": (
            "Professional tone. "
            "Max 5 hashtags. "
            "Under 700 characters."
        ),
        "instagram": (
            "Engaging, visual feel. "
            "5-10 hashtags. "
            "Under 400 characters."
        ),
        "facebook": (
            "Conversational, community feel. "
            "2-3 hashtags. "
            "Under 500 characters."
        ),
    }

    trigger_context = (
        (
            f"Upcoming event : {trigger['name']}\n"
            f"Post angle : {trigger['angle']}"
        )
        if trigger.get("type") == "event"
        else
        (
            f"Trending topic : {trigger['name']}\n"
            f"Post angle : {trigger['angle']}"
        )
    )

    prompt = f"""
You are a social media content writer and art director.

User Profile:
- Persona  : {profile.get('persona')}
- Industry : {profile.get('industry')}
- Brand    : {profile.get('brand_name')}
- Tone     : {profile.get('tone')}
- Audience : {profile.get('audience')}

Platform:
{platform.upper()}

Platform rules:
{platform_rules.get(
    platform,
    "Keep it engaging."
)}

{trigger_context}

Write ONE complete ready-to-publish post,
and ONE image description for an AI image generator
to accompany it.

Rules for the caption:

- Match the tone exactly.
- Feel natural, not AI-generated.
- Include a call to action if relevant.

Rules for the image_prompt:

- Describe a visual SCENE,
  not a restatement of the caption text.
- Reflect the brand's industry, tone, and audience.
- No religious, political, or violent imagery.
- No text, words, logos, or watermarks in the image.
- Keep it to one or two sentences,
  concrete and visual
  (subject, setting, mood).

Return ONLY valid JSON.
Do not return markdown.
Do not return code fences.

{{
  "caption": "the complete ready-to-publish post text",
  "image_prompt": "a short visual scene description for an image generator"
}}
"""

    try:

        raw = generate_llm_response(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=500,
            temperature=0.7,
        )

        raw = (
            raw
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        result = json.loads(raw)

        return {
            "caption": result.get(
                "caption",
                ""
            ).strip(),
            "image_prompt": result.get(
                "image_prompt",
                ""
            ).strip()
        }

    except Exception:

        logger.exception(
            "%s post generation failed",
            AI_PROVIDER
        )

        return {
            "caption": "",
            "image_prompt": ""
        }


def generate_post_content_from_title(
    profile: dict,
    title: str,
    platform: str,
) -> dict:
    """
    Generate social media content from a user-provided title/topic.

    The user only provides the title.
    The application builds the LLM prompt automatically.

    Returns:
        {
            "caption": "...",
            "image_prompt": "..."
        }
    """

    title = (title or "").strip()

    if not title:
        raise ValueError("Title is required.")

    platform_rules = {
        "linkedin": (
            "Professional tone. "
            "Maximum 5 hashtags. "
            "Keep the caption under 700 characters."
        ),
        "instagram": (
            "Engaging and visual tone. "
            "Use 5-10 relevant hashtags. "
            "Keep the caption under 400 characters."
        ),
        "facebook": (
            "Conversational and community-focused tone. "
            "Use 2-3 relevant hashtags. "
            "Keep the caption under 500 characters."
        ),
    }

    prompt = f"""
 You are a professional social media content writer
 and AI image art director.

 USER PROFILE:
 - Persona: {profile.get("persona", "")}
 - Industry: {profile.get("industry", "")}
 - Brand: {profile.get("brand_name", "")}
 - Tone: {profile.get("tone", "professional")}
 - Audience: {profile.get("audience", "")}

 PLATFORM:
 {platform.upper()}

 PLATFORM RULES:
 {platform_rules.get(platform, "Keep the content engaging and natural.")}

 USER-PROVIDED TOPIC:
 {title}

 Your task:

 1. Create ONE ready-to-publish social media caption based
   on the topic.

 2. Create ONE image-generation prompt that visually represents
   the topic.

 IMPORTANT:

 CAPTION:
 - Stay relevant to the topic.
 - Match the brand tone.
 - Match the target audience.
 - Make it natural and useful.
 - Do not invent specific facts.
 - Add a call to action when appropriate.

 IMAGE PROMPT:
 - Create a visual scene related to the topic.
 - Reflect the industry and audience.
 - Make it suitable for a professional social media post.
 - Do not include text, words, logos, or watermarks.
 - Do not simply repeat the caption.
 - Keep the image prompt concrete and visual.

 Return ONLY valid JSON.

  Required JSON format:

 {{
    "caption": "ready-to-publish social media caption",
    "image_prompt": "visual scene description for image generation"
 }}
 """

    try:
        raw = generate_llm_response(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=1200,
            temperature=0.7,
            json_mode=True,
        )

        logger.info(
            "Raw title-based Groq response: %r",
            raw,
        )

        result = json.loads(raw)

        caption = result.get("caption", "").strip()
        image_prompt = result.get("image_prompt", "").strip()

        if not caption:
            raise ValueError("LLM returned an empty caption.")

        if not image_prompt:
            raise ValueError("LLM returned an empty image prompt.")

        return {
            "caption": caption,
            "image_prompt": image_prompt,
        }

    except Exception:
        logger.exception(
            "%s title-based post generation failed",
            AI_PROVIDER,
        )

        return {
            "caption": "",
            "image_prompt": "",
        }

# ============================================================
# IMAGE GENERATION
# ============================================================

async def generate_post_image(
    image_prompt: str,
    profile: dict
) -> bytes:

    if not image_prompt:
        return None

    industry = profile.get(
        "industry",
        ""
    )

    if _is_blocked(
        image_prompt,
        industry
    ):

        logger.info(
            "Blocked image prompt due to content filter"
        )

        return None

    if not POLLINATIONS_API_KEY:

        logger.warning(
            "POLLINATIONS_API_KEY is not configured. "
            "Skipping image generation."
        )

        return None

    tone = profile.get(
        "tone",
        ""
    )

    full_prompt = (
        f"{image_prompt}, "
        f"{tone} mood, "
        f"professional social media photo, "
        f"high quality, "
        f"no text, "
        f"no watermark, "
        f"no logo"
    )

    try:

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:

            resp = await client.get(
                (
                    f"{POLLINATIONS_IMAGE_URL}/"
                    f"{quote(full_prompt)}"
                ),
                params={
                    "model": "flux",
                    "width": 1080,
                    "height": 1080,
                    "nologo": "true"
                },
                headers={
                    "Authorization":
                    f"Bearer {POLLINATIONS_API_KEY}"
                }
            )

            if (
                resp.status_code == 200
                and resp.headers.get(
                    "content-type",
                    ""
                ).startswith("image")
            ):

                return resp.content

            logger.warning(
                "Pollinations returned status %s",
                resp.status_code
            )

            return None

    except Exception:

        logger.exception(
            "Image generation failed"
        )

        return None


# ============================================================
# CLOUDINARY
# ============================================================

def upload_generated_image(
    image_bytes: bytes
) -> str:

    if not image_bytes:
        return None

    try:

        result = cloudinary.uploader.upload(
            image_bytes,
            folder="socialdesk/ai_generated",
            resource_type="image",
            transformation=[
                {
                    "width": 1080,
                    "height": 1080,
                    "crop": "limit"
                },
                {
                    "quality": "auto"
                },
                {
                    "fetch_format": "auto"
                }
            ]
        )

        return result.get(
            "secure_url"
        )

    except Exception:

        logger.exception(
            "Cloudinary upload failed"
        )

        return None


async def generate_media_url(
    image_prompt: str,
    profile: dict
) -> str:

    image_bytes = await generate_post_image(
        image_prompt,
        profile
    )

    if not image_bytes:
        return None

    return upload_generated_image(
        image_bytes
    )


# ============================================================
# REDDIT TRENDS
# ============================================================

async def fetch_reddit_trends(
    industry: str,
    country_code: str
) -> list:

    cached = execute_query(
        """
        SELECT id
        FROM trends_cache
        WHERE country_code = %s
        AND platform = 'reddit'
        AND fetched_at > NOW() - INTERVAL '3 hours'
        LIMIT 1
        """,
        (country_code,),
        fetch="one"
    )

    if cached:

        return execute_query(
            """
            SELECT *
            FROM trends_cache
            WHERE country_code = %s
            AND platform = 'reddit'
            AND fetched_at > NOW() - INTERVAL '3 hours'
            ORDER BY score DESC
            """,
            (country_code,),
            fetch="all"
        ) or []

    INDUSTRY_SUBREDDITS = {
        "tech": [
            "technology",
            "programming",
            "artificial"
        ],
        "marketing": [
            "marketing",
            "socialmedia",
            "digital_marketing"
        ],
        "finance": [
            "investing",
            "personalfinance",
            "entrepreneur"
        ],
        "health": [
            "health",
            "fitness",
            "nutrition"
        ],
        "education": [
            "education",
            "learnprogramming",
            "Teachers"
        ],
        "ecommerce": [
            "ecommerce",
            "entrepreneur",
            "smallbusiness"
        ],
        "design": [
            "design",
            "graphic_design",
            "UI_Design"
        ],
        "saas": [
            "SaaS",
            "startups",
            "entrepreneur"
        ],
    }

    keyword = (
        industry
        .split(",")[0]
        .strip()
        .lower()
    )

    subreddits = INDUSTRY_SUBREDDITS.get(
        keyword,
        [
            "technology",
            "business"
        ]
    )

    topics = []

    try:

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent":
                "socialdesk-trends/1.0"
            }
        ) as client:

            for sub in subreddits[:2]:

                resp = await client.get(
                    f"https://www.reddit.com/r/{sub}/hot.json",
                    params={
                        "limit": 5
                    }
                )

                if resp.status_code != 200:
                    continue

                posts = (
                    resp.json()
                    .get("data", {})
                    .get("children", [])
                )

                for post in posts:

                    title = (
                        post.get("data", {})
                        .get("title", "")
                        .strip()
                    )

                    score = (
                        post.get("data", {})
                        .get("score", 0)
                    )

                    if (
                        title
                        and title not in topics
                    ):

                        topics.append(
                            (
                                title,
                                score
                            )
                        )

    except Exception:

        logger.exception(
            "Reddit trend fetch failed"
        )

        return []

    if not topics:
        return []

    execute_query(
        """
        DELETE FROM trends_cache
        WHERE country_code = %s
        AND platform = 'reddit'
        """,
        (country_code,)
    )

    for title, score in topics[:10]:

        execute_query(
            """
            INSERT INTO trends_cache
                (
                    country_code,
                    platform,
                    topic,
                    score
                )
            VALUES (%s, %s, %s, %s)
            """,
            (
                country_code,
                "reddit",
                title,
                score
            )
        )

    logger.info(
        "Reddit trends fetched for %s",
        country_code
    )

    return execute_query(
        """
        SELECT *
        FROM trends_cache
        WHERE country_code = %s
        AND platform = 'reddit'
        ORDER BY score DESC
        """,
        (country_code,),
        fetch="all"
    ) or []


# ============================================================
# HACKER NEWS
# ============================================================

async def fetch_hackernews_trends() -> list:

    cached = execute_query(
        """
        SELECT id
        FROM trends_cache
        WHERE platform = 'hackernews'
        AND fetched_at > NOW() - INTERVAL '3 hours'
        LIMIT 1
        """,
        fetch="one"
    )

    if cached:

        return execute_query(
            """
            SELECT *
            FROM trends_cache
            WHERE platform = 'hackernews'
            AND fetched_at > NOW() - INTERVAL '3 hours'
            ORDER BY score DESC
            """,
            fetch="all"
        ) or []

    topics = []

    try:

        async with httpx.AsyncClient(
            timeout=15.0
        ) as client:

            resp = await client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )

            top_ids = resp.json()[:10]

            story_resps = await asyncio.gather(
                *[
                    client.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                    )
                    for sid in top_ids
                ],
                return_exceptions=True
            )

            for r in story_resps:

                if isinstance(
                    r,
                    Exception
                ):
                    continue

                story = r.json()

                title = (
                    story.get(
                        "title",
                        ""
                    ).strip()
                )

                score = story.get(
                    "score",
                    0
                )

                if title:

                    topics.append(
                        (
                            title,
                            score
                        )
                    )

    except Exception:

        logger.exception(
            "HackerNews fetch failed"
        )

        return []

    if not topics:
        return []

    execute_query(
        "DELETE FROM trends_cache WHERE platform = 'hackernews'"
    )

    for title, score in topics[:10]:

        execute_query(
            """
            INSERT INTO trends_cache
                (
                    country_code,
                    platform,
                    topic,
                    score
                )
            VALUES (%s, %s, %s, %s)
            """,
            (
                "GLOBAL",
                "hackernews",
                title,
                score
            )
        )

    logger.info(
        "HackerNews trends fetched"
    )

    return execute_query(
        """
        SELECT *
        FROM trends_cache
        WHERE platform = 'hackernews'
        ORDER BY score DESC
        """,
        fetch="all"
    ) or []


# ============================================================
# PRODUCT HUNT
# ============================================================

async def fetch_producthunt_trends() -> list:

    cached = execute_query(
        """
        SELECT id
        FROM trends_cache
        WHERE platform = 'producthunt'
        AND fetched_at > NOW() - INTERVAL '6 hours'
        LIMIT 1
        """,
        fetch="one"
    )

    if cached:

        return execute_query(
            """
            SELECT *
            FROM trends_cache
            WHERE platform = 'producthunt'
            AND fetched_at > NOW() - INTERVAL '6 hours'
            ORDER BY score DESC
            """,
            fetch="all"
        ) or []

    topics = []

    try:

        feed = feedparser.parse(
            "https://www.producthunt.com/feed"
        )

        for entry in feed.entries[:10]:

            title = (
                entry.get(
                    "title",
                    ""
                ).strip()
            )

            if title:
                topics.append(title)

    except Exception:

        logger.exception(
            "ProductHunt fetch failed"
        )

        return []

    if not topics:
        return []

    execute_query(
        "DELETE FROM trends_cache WHERE platform = 'producthunt'"
    )

    for i, title in enumerate(
        topics[:10]
    ):

        execute_query(
            """
            INSERT INTO trends_cache
                (
                    country_code,
                    platform,
                    topic,
                    score
                )
            VALUES (%s, %s, %s, %s)
            """,
            (
                "GLOBAL",
                "producthunt",
                title,
                10 - i
            )
        )

    logger.info(
        "ProductHunt trends fetched"
    )

    return execute_query(
        """
        SELECT *
        FROM trends_cache
        WHERE platform = 'producthunt'
        ORDER BY score DESC
        """,
        fetch="all"
    ) or []


# ============================================================
# GITHUB TRENDING
# ============================================================

async def fetch_github_trending(
    industry: str
) -> list:

    cached = execute_query(
        """
        SELECT id
        FROM trends_cache
        WHERE platform = 'github'
        AND fetched_at > NOW() - INTERVAL '6 hours'
        LIMIT 1
        """,
        fetch="one"
    )

    if cached:

        return execute_query(
            """
            SELECT *
            FROM trends_cache
            WHERE platform = 'github'
            AND fetched_at > NOW() - INTERVAL '6 hours'
            ORDER BY score DESC
            """,
            fetch="all"
        ) or []

    LANGUAGE_MAP = {
        "tech": "python",
        "saas": "javascript",
        "design": "css",
        "data": "jupyter-notebook",
        "mobile": "swift",
    }

    keyword = (
        industry
        .split(",")[0]
        .strip()
        .lower()
    )

    language = LANGUAGE_MAP.get(
        keyword,
        ""
    )

    topics = []

    try:

        url = (
            f"https://github.com/trending/"
            f"{language}?since=daily"
        )

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent":
                "Mozilla/5.0 "
                "(compatible; socialdesk/1.0)"
            }
        ) as client:

            resp = await client.get(url)

            if resp.status_code != 200:

                logger.warning(
                    "GitHub trending returned %s",
                    resp.status_code
                )

                return []

            matches = _re.findall(
                r'href="/([^/"]+/[^/"]+)"[^>]*>\s*\n\s*<span',
                resp.text
            )

            seen = set()

            for m in matches:

                if m not in seen:

                    seen.add(m)
                    topics.append(m)

                if len(topics) >= 10:
                    break

    except Exception:

        logger.exception(
            "GitHub trending fetch failed"
        )

        return []

    if not topics:
        return []

    execute_query(
        "DELETE FROM trends_cache WHERE platform = 'github'"
    )

    for i, repo in enumerate(
        topics[:10]
    ):

        execute_query(
            """
            INSERT INTO trends_cache
                (
                    country_code,
                    platform,
                    topic,
                    score
                )
            VALUES (%s, %s, %s, %s)
            """,
            (
                "GLOBAL",
                "github",
                repo,
                10 - i
            )
        )

    logger.info(
        "GitHub trending fetched"
    )

    return execute_query(
        """
        SELECT *
        FROM trends_cache
        WHERE platform = 'github'
        ORDER BY score DESC
        """,
        fetch="all"
    ) or []


# ============================================================
# RECOMMENDATION PIPELINE
# ============================================================

async def run_recommendation_pipeline(
    user_id: int
) -> list:

    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (user_id,),
        fetch="one"
    )

    if not profile:

        logger.warning(
            "No profile for user %s, skipping",
            user_id
        )

        return []

    country_code = profile.get(
        "country_code",
        "IN"
    )

    industry = profile.get(
        "industry",
        "business"
    )

    connected = execute_query(
        """
        SELECT platform
        FROM social_accounts
        WHERE user_id = %s
        """,
        (user_id,),
        fetch="all"
    )

    platforms = (
        [
            r["platform"]
            for r in connected
        ]
        if connected
        else ["linkedin"]
    )

    logger.info(
        "Platforms configured for user %s: %s",
        user_id,
        platforms
    )

    (
        events,
        google_trends,
        reddit_trends,
        hn_trends,
        ph_trends,
        gh_trends
    ) = await asyncio.gather(
        fetch_holidays(country_code),
        asyncio.to_thread(
            fetch_google_trends,
            country_code,
            industry
        ),
        fetch_reddit_trends(
            industry,
            country_code
        ),
        fetch_hackernews_trends(),
        fetch_producthunt_trends(),
        fetch_github_trending(
            industry
        ),
    )

    all_trends = (
        (google_trends or [])
        + (reddit_trends or [])
        + (hn_trends or [])
        + (ph_trends or [])
        + (gh_trends or [])
    )

    relevant = filter_relevant_events(
        events,
        all_trends,
        profile
    )

    generated_posts = []
    days_offset = 0

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    for event in relevant.get(
        "relevant_events",
        []
    ):

        already_exists = execute_query(
            """
            SELECT sp.id
            FROM scheduled_posts sp
            JOIN post_templates pt
                ON sp.template_id = pt.id
            WHERE pt.user_id = %s
            AND pt.content_text ILIKE %s
            AND sp.created_at::date = CURRENT_DATE
            LIMIT 1
            """,
            (
                user_id,
                f"%{event['event_name'][:20]}%"
            ),
            fetch="one"
        )

        if already_exists:

            logger.info(
                "Skipping duplicate event post: %s",
                event["event_name"]
            )

            continue

        primary_platform = (
            "linkedin"
            if "linkedin" in platforms
            else platforms[0]
        )

        content = generate_post_content(
            profile=profile,
            trigger={
                "type": "event",
                "name": event["event_name"],
                "angle": event["angle"]
            },
            platform=primary_platform
        )

        if not content.get("caption"):
            continue

        media_url = await generate_media_url(
            content.get(
                "image_prompt",
                ""
            ),
            profile
        )

        post_platforms = list(
            platforms
        )

        if (
            not media_url
            and "instagram" in post_platforms
        ):

            logger.info(
                "No image generated; "
                "dropping Instagram for event post: %s",
                event["event_name"]
            )

            post_platforms = [
                p
                for p in post_platforms
                if p != "instagram"
            ]

        try:

            event_date = datetime.strptime(
                event["event_date"],
                "%Y-%m-%d"
            )

            scheduled_at = (
                event_date
                - timedelta(days=3)
            )

            scheduled_at = scheduled_at.replace(
                hour=9,
                minute=0,
                second=0,
                tzinfo=timezone.utc
            )

            if scheduled_at < datetime.now(
                timezone.utc
            ):

                scheduled_at = (
                    datetime.now(
                        timezone.utc
                    )
                    + timedelta(days=1)
                )

                scheduled_at = scheduled_at.replace(
                    hour=9,
                    minute=0,
                    second=0
                )

        except Exception:

            scheduled_at = (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    days=days_offset + 1
                )
            )

        generated_posts.append(
            {
                "content_text":
                    content["caption"],
                "platforms":
                    post_platforms,
                "scheduled_at":
                    scheduled_at,
                "trigger_type":
                    "event",
                "trigger_name":
                    event["event_name"],
                "media_url":
                    media_url
            }
        )

        days_offset += 2

    # --------------------------------------------------------
    # TRENDS
    # --------------------------------------------------------

    for trend in relevant.get(
        "relevant_trends",
        []
    ):

        already_exists = execute_query(
            """
            SELECT sp.id
            FROM scheduled_posts sp
            JOIN post_templates pt
                ON sp.template_id = pt.id
            WHERE pt.user_id = %s
            AND pt.content_text ILIKE %s
            AND sp.created_at::date = CURRENT_DATE
            LIMIT 1
            """,
            (
                user_id,
                f"%{trend['topic'][:20]}%"
            ),
            fetch="one"
        )

        if already_exists:

            logger.info(
                "Skipping duplicate trend post: %s",
                trend["topic"]
            )

            continue

        primary_platform = (
            "linkedin"
            if "linkedin" in platforms
            else platforms[0]
        )

        content = generate_post_content(
            profile=profile,
            trigger={
                "type": "trend",
                "name": trend["topic"],
                "angle": trend["angle"]
            },
            platform=primary_platform
        )

        if not content.get("caption"):
            continue

        media_url = await generate_media_url(
            content.get(
                "image_prompt",
                ""
            ),
            profile
        )

        post_platforms = list(
            platforms
        )

        if (
            not media_url
            and "instagram" in post_platforms
        ):

            logger.info(
                "No image generated; "
                "dropping Instagram for trend post: %s",
                trend["topic"]
            )

            post_platforms = [
                p
                for p in post_platforms
                if p != "instagram"
            ]

        scheduled_at = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                days=days_offset + 1
            )
        )

        scheduled_at = scheduled_at.replace(
            hour=9,
            minute=0,
            second=0
        )

        generated_posts.append(
            {
                "content_text":
                    content["caption"],
                "platforms":
                    post_platforms,
                "scheduled_at":
                    scheduled_at,
                "trigger_type":
                    "trend",
                "trigger_name":
                    trend["topic"],
                "media_url":
                    media_url
            }
        )

        days_offset += 2

    logger.info(
        "Generated %s posts for user %s",
        len(generated_posts),
        user_id
    )

    return generated_posts


def run_recommendation_pipeline_sync(
    user_id: int
) -> list:

    try:

        return asyncio.run(
            run_recommendation_pipeline(
                user_id
            )
        )

    except Exception:

        logger.exception(
            "Failed to run recommendation pipeline "
            "for user %s",
            user_id
        )

        return []