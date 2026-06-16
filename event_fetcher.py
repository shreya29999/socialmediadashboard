# Holidays + Festivals → Calendarific (free, 500 req/month)
# Trends              → Google RSS 
# Post Generation     → Groq API (free tier)

import httpx
import os
import feedparser
import json
from datetime import datetime, timedelta, timezone
from pytrends.request import TrendReq
from groq import Groq
from database import execute_query

CALENDARIFIC_API_KEY = os.getenv("CALENDARIFIC_API_KEY")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY")
groq_client          = Groq(api_key=GROQ_API_KEY)


# SECTION 1 — FETCH HOLIDAYS + FESTIVALS (Calendarific)

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
                print(f"⚠️ No holidays returned for {country_code}: {data}")
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

# SECTION 2 — FETCH TRENDS (pytrends — completely free)

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
        f"https://news.google.com/rss/search?q={industry}&hl={hl}&gl={gl}&ceid={gl}:en",
        f"https://news.google.com/rss/search?q=social+media+trends&hl={hl}&gl={gl}&ceid={gl}:en",
    ]

    topics = []

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:   # top 5 from each feed
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

# SECTION 3 — RELEVANCE FILTER (Groq)

def filter_relevant_events(
    events  : list,
    trends  : list,
    profile : dict
) -> dict:
    if not events and not trends:
        return {"relevant_events": [], "relevant_trends": []}

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

Select maximum 3 events AND maximum 3 trends most relevant 
for this user. For each, give a specific post angle.

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
            model       = "llama-3.3-70b-versatile",
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.3,
            max_tokens  = 800
        )
        raw  = response.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except Exception as e:
        print(f"❌ Groq relevance filter failed: {e}")
        return {"relevant_events": [], "relevant_trends": []}


# SECTION 4 — POST GENERATOR (Groq)

def generate_post_content(
    profile  : dict,
    trigger  : dict,
    platform : str
) -> str:
    platform_rules = {
        "linkedin"  : "Professional tone. Max 3 hashtags. Under 700 characters.",
        "instagram" : "Engaging, visual feel. 5-10 hashtags. Under 400 characters.",
        "facebook"  : "Conversational, community feel. 2-3 hashtags. Under 500 characters."
    }

    trigger_context = (
        f"Upcoming event : {trigger['name']}\nPost angle     : {trigger['angle']}"
        if trigger.get("type") == "event"
        else
        f"Trending topic : {trigger['name']}\nPost angle     : {trigger['angle']}"
    )

    prompt = f"""You are a social media content writer.

User Profile:
- Persona  : {profile.get('persona')}
- Industry : {profile.get('industry')}
- Brand    : {profile.get('brand_name')}
- Tone     : {profile.get('tone')}
- Audience : {profile.get('audience')}

Platform      : {platform.upper()}
Platform rules: {platform_rules.get(platform, "Keep it engaging.")}

{trigger_context}

Write ONE complete ready-to-publish post.
- Match the tone exactly
- Feel natural, not AI-generated
- Include a call to action if relevant
- Return ONLY the post text, nothing else"""

    try:
        response = groq_client.chat.completions.create(
            model       = "llama-3.3-70b-versatile",
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.7,
            max_tokens  = 500
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Groq post generation failed: {e}")
        return ""

# SECTION 5 — MASTER PIPELINE (called by Celery task)

async def run_recommendation_pipeline(user_id: int) -> list:
    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (user_id,), fetch="one"
    )
    if not profile:
        print(f"⚠️ No profile for user {user_id}, skipping")
        return []

    country_code = profile.get("country_code", "IN")
    platforms    = profile.get("platforms") or ["linkedin"]
    events = await fetch_holidays(country_code)
    trends = fetch_google_trends(country_code, profile.get("industry", "business"))
    relevant = filter_relevant_events(events, trends, profile)
    generated_posts = []
    days_offset     = 0
    for event in relevant.get("relevant_events", []):
        for platform in platforms:
            content = generate_post_content(
                profile  = profile,
                trigger  = {
                    "type" : "event",
                    "name" : event["event_name"],
                    "angle": event["angle"]
                },
                platform = platform
            )
            if not content:
                continue
            try:
                event_date   = datetime.strptime(event["event_date"], "%Y-%m-%d")
                scheduled_at = event_date - timedelta(days=3)
                scheduled_at = scheduled_at.replace(
                    hour=9, minute=0, second=0, tzinfo=timezone.utc
                )
            except Exception:
                scheduled_at = datetime.now(timezone.utc) + timedelta(days=days_offset + 1)

            generated_posts.append({
                "content_text" : content,
                "platforms"    : [platform],
                "scheduled_at" : scheduled_at,
                "trigger_type" : "event",
                "trigger_name" : event["event_name"]
            })
            days_offset += 2
    for trend in relevant.get("relevant_trends", []):
        for platform in platforms:
            content = generate_post_content(
                profile  = profile,
                trigger  = {
                    "type" : "trend",
                    "name" : trend["topic"],
                    "angle": trend["angle"]
                },
                platform = platform
            )
            if not content:
                continue

            scheduled_at = datetime.now(timezone.utc) + timedelta(days=days_offset + 1)
            scheduled_at = scheduled_at.replace(hour=9, minute=0, second=0)

            generated_posts.append({
                "content_text" : content,
                "platforms"    : [platform],
                "scheduled_at" : scheduled_at,
                "trigger_type" : "trend",
                "trigger_name" : trend["topic"]
            })
            days_offset += 2

    print(f"✅ Generated {len(generated_posts)} posts for user {user_id}")
    return generated_posts