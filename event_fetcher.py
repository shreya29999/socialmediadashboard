import asyncio
import httpx
import os
import re
import re as _re
import feedparser
import json
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from groq import Groq
import cloudinary
import cloudinary.uploader
from database import execute_query
from logger import logger

CALENDARIFIC_API_KEY  = os.getenv("CALENDARIFIC_API_KEY")
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
POLLINATIONS_API_KEY  = os.getenv("POLLINATIONS_API_KEY")
groq_client           = Groq(api_key=GROQ_API_KEY)
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure     = True
)

POLLINATIONS_IMAGE_URL = "https://gen.pollinations.ai/image"

async def fetch_holidays(country_code: str, year: int = None) -> list:
    if not year:
        year = datetime.now().year
    cached = execute_query("""
        SELECT id FROM events_cache
        WHERE country_code = %s
        AND fetched_at::date = CURRENT_DATE
        LIMIT 1
    """, (country_code,), fetch="one")

    if cached:
        return execute_query("""
            SELECT * FROM events_cache
            WHERE country_code = %s
            AND event_date >= CURRENT_DATE
            AND event_date <= CURRENT_DATE + INTERVAL '30 days'
            ORDER BY event_date ASC
        """, (country_code,), fetch="all") or []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://calendarific.com/api/v2/holidays",
                params={
                    "api_key" : CALENDARIFIC_API_KEY,
                    "country" : country_code,
                    "year"    : year
                }
            )
            data     = resp.json()
            holidays = data.get("response", {}).get("holidays", [])

            if not holidays:
                print(f"No holidays returned for {country_code}: {data}")
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
                event_type = event_type[0] if isinstance(event_type, list) else event_type
                execute_query("""
                    INSERT INTO events_cache
                        (country_code, event_name, event_date, event_type, raw_data)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    country_code,
                    h.get("name"),
                    event_date,
                    event_type,
                    json.dumps(h)
                ))
            print(f"✅ {len(holidays)} holidays/festivals cached for {country_code}")
    except Exception as e:
        print(f"❌ Calendarific fetch failed: {e}")
        return []
    return execute_query("""
        SELECT * FROM events_cache
        WHERE country_code = %s
        AND event_date >= CURRENT_DATE
        AND event_date <= CURRENT_DATE + INTERVAL '30 days'
        ORDER BY event_date ASC
    """, (country_code,), fetch="all") or []


def fetch_google_trends(country_code: str, industry: str) -> list:
    cached = execute_query("""
        SELECT id FROM trends_cache
        WHERE country_code = %s
        AND platform = 'google_news'
        AND fetched_at > NOW() - INTERVAL '6 hours'
        LIMIT 1
    """, (country_code,), fetch="one")

    if cached:
        return execute_query("""
            SELECT * FROM trends_cache
            WHERE country_code = %s AND platform = 'google_news'
            AND fetched_at > NOW() - INTERVAL '6 hours'
            ORDER BY score DESC
        """, (country_code,), fetch="all") or []

    locale_map = {
        "IN": ("en-IN", "IN"),
        "US": ("en-US", "US"),
        "GB": ("en-GB", "GB"),
        "AU": ("en-AU", "AU"),
        "CA": ("en-CA", "CA"),
    }
    hl, gl = locale_map.get(country_code, ("en-IN", "IN"))

    rss_urls = [
        f"https://news.google.com/rss?hl={hl}&gl={gl}&ceid={gl}:en",
        f"https://news.google.com/rss/search?q={quote(industry.split(',')[0].strip())}&hl={hl}&gl={gl}&ceid={gl}:en",
        f"https://news.google.com/rss/search?q=social+media+trends&hl={hl}&gl={gl}&ceid={gl}:en",
    ]

    topics = []

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:  
                title = entry.get("title", "").strip()
                if title and title not in topics:
                    topics.append(title)
        except Exception as e:
            print(f"⚠️ RSS feed failed for {url}: {e}")
            continue

    if not topics:
        print(f"⚠️ No trends fetched for {country_code}")
        return []
    execute_query("""
        DELETE FROM trends_cache
        WHERE country_code = %s AND platform = 'google_news'
    """, (country_code,))
    for i, topic in enumerate(topics[:15]):
        execute_query("""
            INSERT INTO trends_cache
                (country_code, platform, topic, score)
            VALUES (%s, %s, %s, %s)
        """, (country_code, 'google_news', topic, 15 - i))
    print(f"✅ Google News trends fetched for {country_code}: {topics[:3]}")
    return execute_query("""
        SELECT * FROM trends_cache
        WHERE country_code = %s AND platform = 'google_news'
        ORDER BY score DESC
    """, (country_code,), fetch="all") or []
EXCLUDED_EVENT_TYPES = {
    "religious",
    "observance",      
    "national",         
}
BASE_EXCLUDED_KEYWORDS = [
    "christmas", "easter","hanukkah", "passover",
    "good friday", "navratri", "puja", "church", "mosque", "temple", "holy",
    "saint", "prophet", "religious", "pilgrimage", "hajj", "yom kippur",
    "election", "president", "minister", "parliament", "senate", "congress",
    "political", "protest", "referendum", "coup", "rebellion", "uprising",
    "vote", "campaign", "party leader", "republic day", "independence day",
    "constitution day","terrorist","terrorism",
    "war", "attack", "shooting", "bombing", "terror", "assassination",
    "riot", "violence", "killed", "massacre", "conflict", "military strike",
]
INDUSTRY_EXTRA_KEYWORDS = {
    "tech": [
        "martyr", "war memorial", "armed forces", "military",
    ],
}

def _is_blocked(text: str, industry: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    keywords = BASE_EXCLUDED_KEYWORDS + INDUSTRY_EXTRA_KEYWORDS.get(
        (industry or "").lower(), []
    )
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text_lower):
            return True
    return False

def _prefilter_events(events: list, industry: str) -> list:
    safe = []
    for e in events or []:
        event_type = (e.get("event_type") or "").lower()
        if event_type in EXCLUDED_EVENT_TYPES:
            print(f"🚫 Excluded event (type={event_type}): {e.get('event_name')}")
            continue
        if _is_blocked(e.get("event_name", ""), industry):
            print(f"🚫 Excluded event (keyword match): {e.get('event_name')}")
            continue
        safe.append(e)
    return safe


def _prefilter_trends(trends: list, industry: str) -> list:
    safe = []
    for t in trends or []:
        if _is_blocked(t.get("topic", ""), industry):
            print(f"🚫 Excluded trend (keyword match): {t.get('topic')}")
            continue
        safe.append(t)
    return safe

def _postfilter_groq_output(result: dict, industry: str) -> dict:
    clean_events = []
    for e in result.get("relevant_events", []):
        if _is_blocked(e.get("event_name", ""), industry) or _is_blocked(
            e.get("angle", ""), industry
        ):
            print(f"🚫 Post-filter dropped event: {e.get('event_name')}")
            continue
        clean_events.append(e)
    clean_trends = []
    for t in result.get("relevant_trends", []):
        if _is_blocked(t.get("topic", ""), industry) or _is_blocked(
            t.get("angle", ""), industry
        ):
            print(f"🚫 Post-filter dropped trend: {t.get('topic')}")
            continue
        clean_trends.append(t)

    return {"relevant_events": clean_events, "relevant_trends": clean_trends}

def filter_relevant_events(
    events  : list,
    trends  : list,
    profile : dict
) -> dict:
    industry = profile.get("industry", "")
    events = _prefilter_events(events, industry)
    trends = _prefilter_trends(trends, industry)
    if not events and not trends:
        return {"relevant_events": [],"relevant_trends": []}

    events_list = [
        f"- {e['event_name']} on {e['event_date']} (type: {e['event_type']})"
        for e in (events or [])
    ]
    trends_list = [
        f"- {t['topic']}"
        for t in (trends or [])[:10]
    ]
    prompt = f"""You are a social media strategist.

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

STRICT CONTENT RULES (apply to every event/trend you select AND to the angle you write):
- Do NOT select or reference anything religious (festivals, religious holidays, religious figures, places of worship).
- Do NOT select or reference anything political (elections, politicians, parties, protests, government policy debates).
- Do NOT select or reference anything violent, tragic, or related to war, conflict, attacks, or death.
- If nothing qualifies, return empty lists. Do not force a selection.
Select maximum 3 events AND maximum 3 trends most relevant 
for this user, respecting the rules above. For each, give a specific post angle.

Return ONLY valid JSON, no explanation, no markdown:
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
}}"""
    try:
        response = groq_client.chat.completions.create(
            model       = "meta-llama/llama-4-scout-17b-16e-instruct",
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.3,
            max_tokens  = 800
        )
        raw  = response.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

    except Exception as e:
        print(f"❌ Groq relevance filter failed: {e}")
        return {"relevant_events": [], "relevant_trends": []}
    return _postfilter_groq_output(result, industry)

def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())

STOPWORDS = {
    "what", "when", "where", "which", "who", "how", "why",
    "should", "could", "would", "will", "can", "may", "might",
    "the", "and", "for", "are", "was", "were", "been", "being",
    "have", "has", "had", "did", "does", "this", "that", "with",
    "from", "your", "our", "their", "his", "her", "its", "you",
    "they", "them", "some", "any", "all", "more", "also", "just",
    "about", "into", "than", "then", "now", "not", "but", "out",
    "give", "tell", "show", "get", "make", "use", "need", "want",
    "like", "help", "know", "see", "look", "think", "much", "many"
}

def _get_query_tokens(query: str) -> set:
    return {
        token for token in _normalize_text(query).split()
        if len(token) > 2 and token not in STOPWORDS
    }

def _score_doc_text(text: str, query_tokens: set) -> int:
    tokens = _normalize_text(text).split()
    return sum(1 for t in tokens if t in query_tokens)

def _get_rag_documents(user_id: int) -> list:
    docs = []
    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (user_id,), fetch="one"
    ) or {}

    if profile:
        docs.append({
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
        })

    recent_posts = execute_query(
        "SELECT content_text, platforms, created_at FROM post_templates WHERE user_id = %s ORDER BY created_at DESC LIMIT 8",
        (user_id,), fetch="all"
    ) or []
    for post in recent_posts:
        docs.append({
            "source": "Recent post",
            "title": post.get("created_at", "Recent post"),
            "content": (
                f"Content: {post.get('content_text', '')}\n"
                f"Platforms: {', '.join(post.get('platforms', []) or [])}"
            )
        })

    country_code = profile.get("country_code") if profile else None
    if country_code:
        events = execute_query(
            "SELECT event_name, event_date, event_type FROM events_cache WHERE country_code = %s ORDER BY event_date ASC LIMIT 8",
            (country_code,), fetch="all"
        ) or []
        for event in events:
            docs.append({
                "source": "Upcoming event",
                "title": event.get("event_name", "Event"),
                "content": (
                    f"Event: {event.get('event_name', '')}\n"
                    f"Date: {event.get('event_date', '')}\n"
                    f"Type: {event.get('event_type', '')}"
                )
            })
        trends = execute_query(
            "SELECT topic FROM trends_cache WHERE country_code = %s ORDER BY score DESC LIMIT 8",
            (country_code,), fetch="all"
        ) or []
        for trend in trends:
            docs.append({
                "source": "Trending topic",
                "title": trend.get("topic", "Trend"),
                "content": f"Topic: {trend.get('topic', '')}"
            })

    return docs


def retrieve_rag_documents(user_id: int, query: str, limit: int = 4) -> list:
    docs = _get_rag_documents(user_id)
    query_tokens = _get_query_tokens(query)
    scored = [
        (_score_doc_text(doc["content"], query_tokens), doc)
        for doc in docs
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [doc for score, doc in scored if score > 0][:limit]
    if not selected:
        selected = [doc for _, doc in scored[:limit]]
    return selected

def _get_chat_history(user_id: int, limit: int = 6) -> list:
    rows = execute_query("""
        SELECT role, content FROM rag_chat_history
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (user_id, limit), fetch="all") or []
    return list(reversed(rows))


def _save_chat_turn(user_id: int, role: str, content: str):
    execute_query("""
        INSERT INTO rag_chat_history (user_id, role, content)
        VALUES (%s, %s, %s)
    """, (user_id, role, content))

def answer_rag_query(user_id: int, query: str) -> dict:
    docs    = retrieve_rag_documents(user_id, query, limit=5)
    sources = [f"{doc['source']} - {doc['title']}" for doc in docs]
    context = "\n\n".join([
        f"Source: {doc['source']}\n{doc['content']}" for doc in docs
    ]) or "No relevant documents found."

    history = _get_chat_history(user_id, limit=6)

    system_prompt = f"""You are a helpful social media assistant.
Only use the information in the context below. Do not invent facts.
If the question is outside this context, say so.
Context:
{context}"""

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": query})

    try:
        response = groq_client.chat.completions.create(
            model       = "meta-llama/llama-4-scout-17b-16e-instruct",
            messages    = messages,         
            temperature = 0.2,
            max_tokens  = 450
        )
        answer = response.choices[0].message.content.strip()
        _save_chat_turn(user_id, "user",      query)
        _save_chat_turn(user_id, "assistant", answer)

        return {"answer": answer, "sources": sources}

    except Exception as e:
        print(f"❌ Groq RAG query failed: {e}")
        return {"answer": "Could not answer right now.", "sources": sources}

def generate_post_content(
    profile  : dict,
    trigger  : dict,
    platform : str
) -> dict:
    platform_rules = {
        "linkedin"  : "Professional tone. Max 5 hashtags. Under 700 characters.",
        "instagram" : "Engaging, visual feel. 5-10 hashtags. Under 400 characters.",
        "facebook"  : "Conversational, community feel. 2-3 hashtags. Under 500 characters."
    }

    trigger_context = (
        f"Upcoming event : {trigger['name']}\nPost angle :{trigger['angle']}"
        if trigger.get("type") == "event"
        else
        f"Trending topic : {trigger['name']}\nPost angle :{trigger['angle']}"
    )

    prompt = f"""You are a social media content writer and art director.

User Profile:
- Persona  : {profile.get('persona')}
- Industry : {profile.get('industry')}
- Brand    : {profile.get('brand_name')}
- Tone     : {profile.get('tone')}
- Audience : {profile.get('audience')}

Platform      : {platform.upper()}
Platform rules: {platform_rules.get(platform, "Keep it engaging.")}
{trigger_context}
Write ONE complete ready-to-publish post, and ONE image description for an AI
image generator to accompany it.
Rules for the caption:
- Match the tone exactly
- Feel natural, not AI-generated
- Include a call to action if relevant
Rules for the image_prompt:
- Describe a visual SCENE, not a restatement of the caption text
- Reflect the brand's industry, tone, and audience
- No religious, political, or violent imagery
- No text, words, logos, or watermarks in the image
- Keep it to one or two sentences, concrete and visual (subject, setting, mood)
Return ONLY valid JSON, no explanation, no markdown:
{{
  "caption": "the complete ready-to-publish post text",
  "image_prompt": "a short visual scene description for an image generator"
}}"""

    try:
        response = groq_client.chat.completions.create(
            model       = "meta-llama/llama-4-scout-17b-16e-instruct",
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.7,
            max_tokens  = 500
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return {
            "caption"     : result.get("caption", "").strip(),
            "image_prompt": result.get("image_prompt", "").strip()
        }

    except Exception as e:
        print(f"❌ Groq post generation failed: {e}")
        return {"caption": "", "image_prompt": ""}


async def generate_post_image(image_prompt: str, profile: dict) -> bytes:
    if not image_prompt:
        return None

    industry = profile.get("industry", "")
    if _is_blocked(image_prompt, industry):
        print(f"🚫 Blocked image prompt (keyword match): {image_prompt}")
        return None

    if not POLLINATIONS_API_KEY:
        print("❌ POLLINATIONS_API_KEY not set — skipping image generation. "
              "Get a free key at https://enter.pollinations.ai and add it to .env")
        return None

    tone = profile.get("tone", "")
    full_prompt = (
        f"{image_prompt}, {tone} mood, professional social media photo, "
        f"high quality, no text, no watermark, no logo"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{POLLINATIONS_IMAGE_URL}/{quote(full_prompt)}",
                params={
                    "model"  : "flux",
                    "width"  : 1080,
                    "height" : 1080,
                    "nologo" : "true"
                },
                headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"}
            )
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                return resp.content
            print(f"⚠️ Pollinations returned status {resp.status_code}")
            return None
    except Exception as e:
        print(f"❌ Image generation failed: {e}")
        return None

def upload_generated_image(image_bytes: bytes) -> str:
    if not image_bytes:
        return None
    try:
        result = cloudinary.uploader.upload(
            image_bytes,
            folder = "socialdesk/ai_generated",
            resource_type  = "image",
            transformation = [
                {"width": 1080, "height": 1080, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {e}")
        return None


async def generate_media_url(image_prompt: str, profile: dict) -> str:
    image_bytes = await generate_post_image(image_prompt, profile)
    if not image_bytes:
        return None
    return upload_generated_image(image_bytes)


async def fetch_reddit_trends(industry: str, country_code: str) -> list:
    cached = execute_query("""
        SELECT id FROM trends_cache
        WHERE country_code = %s AND platform = 'reddit'
        AND fetched_at > NOW() - INTERVAL '3 hours'
        LIMIT 1
    """, (country_code,), fetch="one")

    if cached:
        return execute_query("""
            SELECT * FROM trends_cache
            WHERE country_code = %s AND platform = 'reddit'
            AND fetched_at > NOW() - INTERVAL '3 hours'
            ORDER BY score DESC
        """, (country_code,), fetch="all") or []
    INDUSTRY_SUBREDDITS = {
        "tech"          : ["technology", "programming", "artificial"],
        "marketing"     : ["marketing", "socialmedia", "digital_marketing"],
        "finance"       : ["investing", "personalfinance", "entrepreneur"],
        "health"        : ["health", "fitness", "nutrition"],
        "education"     : ["education", "learnprogramming", "Teachers"],
        "ecommerce"     : ["ecommerce", "entrepreneur", "smallbusiness"],
        "design"        : ["design", "graphic_design", "UI_Design"],
        "saas"          : ["SaaS", "startups", "entrepreneur"],
    }
    keyword = industry.split(",")[0].strip().lower()
    subreddits = INDUSTRY_SUBREDDITS.get(keyword, ["technology", "business"])
    topics = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "socialdesk-trends/1.0"}) as client:
            for sub in subreddits[:2]:
                resp = await client.get(
                    f"https://www.reddit.com/r/{sub}/hot.json",
                    params={"limit": 5}
                )
                if resp.status_code != 200:
                    continue
                posts = resp.json().get("data", {}).get("children", [])
                for post in posts:
                    title = post.get("data", {}).get("title", "").strip()
                    score = post.get("data", {}).get("score", 0)
                    if title and title not in topics:
                        topics.append((title, score))
    except Exception as e:
        print(f"Reddit fetch failed: {e}")
        return []
    if not topics:
        return []
    execute_query("""
        DELETE FROM trends_cache
        WHERE country_code = %s AND platform = 'reddit'
    """, (country_code,))
    for title, score in topics[:10]:
        execute_query("""
            INSERT INTO trends_cache (country_code, platform, topic, score)
            VALUES (%s, %s, %s, %s)
        """, (country_code, "reddit", title, score))

    print(f"Reddit trends fetched: {[t for t, _ in topics[:3]]}")
    return execute_query("""
        SELECT * FROM trends_cache
        WHERE country_code = %s AND platform = 'reddit'
        ORDER BY score DESC
    """, (country_code,), fetch="all") or []


async def fetch_hackernews_trends() -> list:
    cached = execute_query("""
        SELECT id FROM trends_cache
        WHERE platform = 'hackernews'
        AND fetched_at > NOW() - INTERVAL '3 hours'
        LIMIT 1
    """, fetch="one")
    if cached:
        return execute_query("""
            SELECT * FROM trends_cache
            WHERE platform = 'hackernews'
            AND fetched_at > NOW() - INTERVAL '3 hours'
            ORDER BY score DESC
        """, fetch="all") or []

    topics = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp    = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            top_ids = resp.json()[:10]
            story_resps = await asyncio.gather(
                *[client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                  for sid in top_ids],
                return_exceptions=True
            )
            for r in story_resps:
                if isinstance(r, Exception):
                    continue
                story = r.json()
                title = story.get("title", "").strip()
                score = story.get("score", 0)
                if title:
                    topics.append((title, score))

    except Exception as e:
        print(f"HackerNews fetch failed: {e}")
        return []

    if not topics:
        return []

    execute_query("DELETE FROM trends_cache WHERE platform = 'hackernews'")
    for title, score in topics[:10]:
        execute_query("""
            INSERT INTO trends_cache (country_code, platform, topic, score)
            VALUES (%s, %s, %s, %s)
        """, ("GLOBAL", "hackernews", title, score))

    print(f"HackerNews trends fetched: {[t for t, _ in topics[:3]]}")
    return execute_query("""
        SELECT * FROM trends_cache
        WHERE platform = 'hackernews'
        ORDER BY score DESC
    """, fetch="all") or []

async def fetch_producthunt_trends() -> list:
    cached = execute_query("""
        SELECT id FROM trends_cache
        WHERE platform = 'producthunt'
        AND fetched_at > NOW() - INTERVAL '6 hours'
        LIMIT 1
    """, fetch="one")

    if cached:
        return execute_query("""
            SELECT * FROM trends_cache
            WHERE platform = 'producthunt'
            AND fetched_at > NOW() - INTERVAL '6 hours'
            ORDER BY score DESC
        """, fetch="all") or []

    topics = []
    try:
        feed = feedparser.parse("https://www.producthunt.com/feed")
        for entry in feed.entries[:10]:
            title   = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            if title:
                topics.append(title)
    except Exception as e:
        print(f"ProductHunt fetch failed: {e}")
        return []

    if not topics:
        return []

    execute_query("DELETE FROM trends_cache WHERE platform = 'producthunt'")
    for i, title in enumerate(topics[:10]):
        execute_query("""
            INSERT INTO trends_cache (country_code, platform, topic, score)
            VALUES (%s, %s, %s, %s)
        """, ("GLOBAL", "producthunt", title, 10 - i))

    print(f"ProductHunt trends fetched: {topics[:3]}")
    return execute_query("""
        SELECT * FROM trends_cache
        WHERE platform = 'producthunt'
        ORDER BY score DESC
    """, fetch="all") or []


async def fetch_github_trending(industry: str) -> list:
    cached = execute_query("""
        SELECT id FROM trends_cache
        WHERE platform = 'github'
        AND fetched_at > NOW() - INTERVAL '6 hours'
        LIMIT 1
    """, fetch="one")

    if cached:
        return execute_query("""
            SELECT * FROM trends_cache
            WHERE platform = 'github'
            AND fetched_at > NOW() - INTERVAL '6 hours'
            ORDER BY score DESC
        """, fetch="all") or []
    LANGUAGE_MAP = {
        "tech"       : "python",
        "saas"       : "javascript",
        "design"     : "css",
        "data"       : "jupyter-notebook",
        "mobile"     : "swift",
    }
    keyword  = industry.split(",")[0].strip().lower()
    language = LANGUAGE_MAP.get(keyword, "")

    topics = []
    try:
        url = f"https://github.com/trending/{language}?since=daily"
        async with httpx.AsyncClient(timeout=15.0, headers={
            "User-Agent": "Mozilla/5.0 (compatible; socialdesk/1.0)"
        }) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                print(f"GitHub trending returned {resp.status_code}")
                return []
            matches = _re.findall(r'href="/([^/"]+/[^/"]+)"[^>]*>\s*\n\s*<span', resp.text)
            seen = set()
            for m in matches:
                if m not in seen:
                    seen.add(m)
                    topics.append(m)
                if len(topics) >= 10:
                    break
    except Exception as e:
        print(f"GitHub trending fetch failed: {e}")
        return []

    if not topics:
        return []

    execute_query("DELETE FROM trends_cache WHERE platform = 'github'")
    for i, repo in enumerate(topics[:10]):
        execute_query("""
            INSERT INTO trends_cache (country_code, platform, topic, score)
            VALUES (%s, %s, %s, %s)
        """, ("GLOBAL", "github", repo, 10 - i))

    print(f"GitHub trending fetched: {topics[:3]}")
    return execute_query("""
        SELECT * FROM trends_cache
        WHERE platform = 'github'
        ORDER BY score DESC
    """, fetch="all") or []              
    

async def run_recommendation_pipeline(user_id: int) -> list:
    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (user_id,), fetch="one"
    )
    if not profile:
        print(f"No profile for user {user_id}, skipping")
        return []

    country_code = profile.get("country_code", "IN")
    industry     = profile.get("industry", "business")
    connected    = execute_query(
        "SELECT platform FROM social_accounts WHERE user_id = %s",
        (user_id,), fetch="all"
    )
    platforms = [r["platform"] for r in connected] if connected else ["linkedin"]
    print(f"📱 Platforms for user {user_id}: {platforms}")
    (
        events,
        google_trends,
        reddit_trends,
        hn_trends,
        ph_trends,
        gh_trends
    ) = await asyncio.gather(
        fetch_holidays(country_code),
        asyncio.to_thread(fetch_google_trends, country_code, industry),
        fetch_reddit_trends(industry, country_code),
        fetch_hackernews_trends(),
        fetch_producthunt_trends(),
        fetch_github_trending(industry),
    )

    all_trends = (google_trends or []) + (reddit_trends or []) + \
                 (hn_trends    or []) + (ph_trends    or []) + \
                 (gh_trends    or [])

    relevant        = filter_relevant_events(events, all_trends, profile)
    generated_posts = []
    days_offset     = 0

    for event in relevant.get("relevant_events", []):
        already_exists = execute_query("""
            SELECT sp.id FROM scheduled_posts sp
            JOIN post_templates pt ON sp.template_id = pt.id
            WHERE pt.user_id = %s
            AND pt.content_text ILIKE %s
            AND sp.created_at::date = CURRENT_DATE
            LIMIT 1
        """, (user_id, f"%{event['event_name'][:20]}%"), fetch="one")

        if already_exists:
            print(f"Skipping duplicate for event: {event['event_name']}")
            continue

        primary_platform = "linkedin" if "linkedin" in platforms else platforms[0]
        content = generate_post_content(
            profile  = profile,
            trigger  = {
                "type" : "event",
                "name" : event["event_name"],
                "angle": event["angle"]
            },
            platform = primary_platform
        )
        if not content.get("caption"):
            continue

        media_url      = await generate_media_url(content.get("image_prompt", ""), profile)
        post_platforms = list(platforms)
        if not media_url and "instagram" in post_platforms:
            print(f"No image generated — dropping Instagram for event post: {event['event_name']}")
            post_platforms = [p for p in post_platforms if p != "instagram"]

        try:
            event_date   = datetime.strptime(event["event_date"], "%Y-%m-%d")
            scheduled_at = event_date - timedelta(days=3)
            scheduled_at = scheduled_at.replace(hour=9, minute=0, second=0, tzinfo=timezone.utc)
            if scheduled_at < datetime.now(timezone.utc):
                scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
                scheduled_at = scheduled_at.replace(hour=9, minute=0, second=0)
        except Exception:
            scheduled_at = datetime.now(timezone.utc) + timedelta(days=days_offset + 1)

        generated_posts.append({
            "content_text" : content["caption"],
            "platforms"    : post_platforms,
            "scheduled_at" : scheduled_at,
            "trigger_type" : "event",
            "trigger_name" : event["event_name"],
            "media_url"    : media_url
        })
        days_offset += 2

    for trend in relevant.get("relevant_trends", []):
        already_exists = execute_query("""
            SELECT sp.id FROM scheduled_posts sp
            JOIN post_templates pt ON sp.template_id = pt.id
            WHERE pt.user_id = %s
            AND pt.content_text ILIKE %s
            AND sp.created_at::date = CURRENT_DATE
            LIMIT 1
        """, (user_id, f"%{trend['topic'][:20]}%"), fetch="one")

        if already_exists:
            print(f"Skipping duplicate for trend: {trend['topic']}")
            continue

        primary_platform = "linkedin" if "linkedin" in platforms else platforms[0]
        content = generate_post_content(
            profile  = profile,
            trigger  = {
                "type" : "trend",
                "name" : trend["topic"],
                "angle": trend["angle"]
            },
            platform = primary_platform
        )
        if not content.get("caption"):
            continue

        media_url      = await generate_media_url(content.get("image_prompt", ""), profile)
        post_platforms = list(platforms)
        if not media_url and "instagram" in post_platforms:
            print(f"No image generated — dropping Instagram for trend post: {trend['topic']}")
            post_platforms = [p for p in post_platforms if p != "instagram"]

        scheduled_at = datetime.now(timezone.utc) + timedelta(days=days_offset + 1)
        scheduled_at = scheduled_at.replace(hour=9, minute=0, second=0)

        generated_posts.append({
            "content_text" : content["caption"],
            "platforms"    : post_platforms,
            "scheduled_at" : scheduled_at,
            "trigger_type" : "trend",
            "trigger_name" : trend["topic"],
            "media_url"    : media_url
        })
        days_offset += 2

    logger.info("Generated %s posts for user %s", len(generated_posts), user_id)
    return generated_posts


def run_recommendation_pipeline_sync(user_id: int) -> list:
    try:
        return asyncio.run(run_recommendation_pipeline(user_id))
    except Exception:
        logger.exception("Failed to run recommendation pipeline for user %s", user_id)
        return []