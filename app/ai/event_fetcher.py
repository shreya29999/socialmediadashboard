import asyncio
import numpy as np
import cv2
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

from app.repositories.cache_repository import (
    get_cached_events,
    has_fresh_events_cache,
    delete_events_cache,
    save_event,
    has_fresh_trends_cache,
    get_cached_trends,
    delete_trends_cache,
    save_trend,
)

from app.repositories.rag_repository import (
    get_rag_profile,
    get_recent_posts_for_rag,
    get_events_for_rag,
    get_trends_for_rag,
    get_chat_history,
    save_chat_turn,
)
from app.repositories.user_repository import get_user_profile
from app.repositories.recommendation_repository import (
    get_connected_platforms,
    has_duplicate_post_for_trigger,
)

from app.core.logging import logger
from app.ai.llm import generate_llm_response, AI_PROVIDER

# ============================================================
# CONFIGURATION
# ============================================================

CALENDARIFIC_API_KEY = os.getenv("CALENDARIFIC_API_KEY")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")

#Open CV 


def prepare_logo_with_opencv(logo_bytes: bytes) -> np.ndarray | None:
    """
    Remove the white background from a logo image and crop
    the result to the actual logo content.
    """

    logo_array = np.frombuffer(logo_bytes, dtype=np.uint8)

    logo = cv2.imdecode(
        logo_array,
        cv2.IMREAD_UNCHANGED,
    )

    if logo is None:
        logger.error("Unable to decode company logo")
        return None

    # If logo already has alpha, use it directly.
    if logo.ndim == 3 and logo.shape[2] == 4:
        return logo

    # Convert to BGR if necessary.
    logo = logo[:, :, :3]

    # Calculate distance from white.
    # White pixels have all channels close to 255.
    min_channel = np.min(
        logo,
        axis=2,
    ).astype(np.float32)

    alpha = 1.0 - (
        min_channel / 255.0
    )

    # Remove almost-white pixels.
    alpha[alpha < 0.10] = 0.0

    # Keep actual logo pixels.
    alpha[alpha >= 0.10] = 1.0

    # Smooth the boundary.
    alpha = cv2.GaussianBlur(
        alpha,
        (5, 5),
        0,
    )

    # Find the actual logo area.
    mask = (
        alpha > 0.08
    ).astype(np.uint8) * 255

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if not contours:
        logger.warning(
            "No visible logo content detected"
        )
        return None

    x, y, w, h = cv2.boundingRect(
        np.vstack(contours)
    )

    # Small padding around the actual logo.
    padding = 5

    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(logo.shape[1], x + w + padding)
    y2 = min(logo.shape[0], y + h + padding)

    logo = logo[y1:y2, x1:x2]
    alpha = alpha[y1:y2, x1:x2]

    alpha = (
        alpha * 255
    ).astype(np.uint8)

    # Create RGBA logo.
    logo_rgba = cv2.cvtColor(
        logo,
        cv2.COLOR_BGR2BGRA,
    )

    logo_rgba[:, :, 3] = alpha

    return logo_rgba


async def apply_logo_with_opencv(
    image_bytes: bytes,
    logo_url: str | None,
) -> bytes|None:
    if not image_bytes:
        return None

    if not logo_url:
        logger.info("No company logo configured; returning original image")
        return image_bytes

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(logo_url)
            response.raise_for_status()

        base_array = np.frombuffer(image_bytes, dtype=np.uint8)
        logo_array = np.frombuffer(response.content, dtype=np.uint8)

        base_image = cv2.imdecode(
            base_array,
            cv2.IMREAD_COLOR,
        )

        logo_image = cv2.imdecode(
            logo_array,
            cv2.IMREAD_UNCHANGED,
        )

        if base_image is None:
            logger.error("Unable to decode generated image with OpenCV")
            return image_bytes

        if logo_image is None:
            logger.error("Unable to decode company logo with OpenCV")
            return image_bytes

        base_height, base_width = base_image.shape[:2]

        target_logo_width = max(
            1,
            base_width // 6,
        )

        logo_height, logo_width = logo_image.shape[:2]

        scale = target_logo_width / logo_width

        target_logo_height = max(
            1,
            int(logo_height * scale),
        )

        logo_image = cv2.resize(
            logo_image,
            (target_logo_width, target_logo_height),
            interpolation=cv2.INTER_AREA,
        )


        margin = 40
        x1 = margin
        y1 = margin



        x2 = x1 + target_logo_width
        y2 = y1 + target_logo_height

        if x1 < 0 or y1 < 0:
            logger.warning(
                "Company logo is too large for generated image"
            )
            return image_bytes

        roi = base_image[y1:y2, x1:x2]

        if logo_image.shape[2] == 4:
        
            logo_rgb = logo_image[:, :, :3]

            alpha = logo_image[:, :, 3].astype(np.float32) / 255.0

        else:

            logo_rgb = logo_image[:, :, :3]
            min_channel = np.min(logo_rgb, axis=2).astype(np.float32)
            alpha = (255.0 - min_channel) / 255.0
            alpha[alpha < 0.08] = 0.0
            alpha[alpha > 0.35] = 1.0
            alpha = cv2.GaussianBlur(
                alpha,
                (5, 5),
                0,
            )

        alpha = alpha[:, :, np.newaxis]

        blended = (
            logo_rgb.astype(np.float32) * alpha
            + roi.astype(np.float32) * (1.0 - alpha)
        )

        base_image[y1:y2, x1:x2] = np.clip(
            blended,
            0,
            255,
        ).astype(np.uint8)

        success, encoded_image = cv2.imencode(
            ".jpg",
            base_image,
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )

        if not success:
            logger.error("Failed to encode branded image")
            return image_bytes

        logger.info(
            "Company logo successfully applied to generated image"
        )

        return encoded_image.tobytes()

    except Exception:
        logger.exception(
            "Failed to apply company logo with OpenCV"
        )
        return image_bytes

async def apply_overlay_text_with_opencv(
    image_bytes: bytes,
    overlay_text: str | None,
    overlay_position: str,
    overlay_text_size: int = 48,
) -> bytes | None:
    if not image_bytes:
        return None

    if not overlay_text or not overlay_text.strip():
        logger.info(
            "No custom overlay text configured; returning original image"
        )
        return image_bytes

    allowed_positions = {
        "top-left",
        "top-center",
        "top-right",
        "center-left",
        "center",
        "center-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    }

    if overlay_position not in allowed_positions:
        logger.warning(
            "Invalid overlay position '%s'; using bottom-center",
            overlay_position,
        )
        overlay_position = "bottom-center"

    try:
        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            logger.error(
                "Unable to decode generated image for overlay text"
            )
            return image_bytes

        height, width = image.shape[:2]

        # ---------------------------------------------------------
        # USER SELECTED TEXT SIZE
        # ---------------------------------------------------------

        try:
            text_size = int(overlay_text_size)
        except (TypeError, ValueError):
            text_size = 48

        # Prevent unusable values
        text_size = max(16, min(text_size, 150))

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Convert requested pixel size into OpenCV font scale
        font_scale = text_size / 30.0

        thickness = max(
            2,
            int(text_size / 18),
        )

        outline_thickness = thickness + 3

        margin = 40

        text = overlay_text.strip()

        if not text:
            logger.info(
                "Overlay text is empty; returning original image"
            )
            return image_bytes

        # ---------------------------------------------------------
        # AUTOMATIC TEXT WRAPPING
        # ---------------------------------------------------------

        max_text_width = width - (2 * margin)

        words = text.split()

        lines = []
        current_line = ""

        for word in words:
            test_line = (
                word
                if not current_line
                else f"{current_line} {word}"
            )

            (test_width, _), _ = cv2.getTextSize(
                test_line,
                font,
                font_scale,
                thickness,
            )

            if test_width <= max_text_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)

                current_line = word

        if current_line:
            lines.append(current_line)

        if not lines:
            logger.warning(
                "Overlay text could not be wrapped"
            )
            return image_bytes

        # ---------------------------------------------------------
        # CALCULATE TEXT DIMENSIONS
        # ---------------------------------------------------------

        line_data = []

        for line in lines:
            (line_width, line_height), baseline = cv2.getTextSize(
                line,
                font,
                font_scale,
                thickness,
            )

            line_data.append(
                {
                    "width": line_width,
                    "height": line_height,
                    "baseline": baseline,
                }
            )

        line_spacing = max(
            10,
            int(text_size * 0.35),
        )

        total_text_height = sum(
            item["height"] + item["baseline"]
            for item in line_data
        )

        total_text_height += (
            line_spacing * (len(lines) - 1)
        )

        max_line_width = max(
            item["width"]
            for item in line_data
        )

        # ---------------------------------------------------------
        # CALCULATE START POSITION
        # ---------------------------------------------------------

        if overlay_position == "top-left":
            start_y = margin + line_data[0]["height"]

        elif overlay_position == "top-center":
            start_y = margin + line_data[0]["height"]

        elif overlay_position == "top-right":
            start_y = margin + line_data[0]["height"]

        elif overlay_position == "center-left":
            start_y = (
                height - total_text_height
            ) // 2 + line_data[0]["height"]

        elif overlay_position == "center":
            start_y = (
                height - total_text_height
            ) // 2 + line_data[0]["height"]

        elif overlay_position == "center-right":
            start_y = (
                height - total_text_height
            ) // 2 + line_data[0]["height"]

        else:
            start_y = (
                height
                - total_text_height
                - margin
                + line_data[0]["height"]
            )

        # ---------------------------------------------------------
        # DRAW EACH LINE
        # ---------------------------------------------------------

        current_y = start_y

        for index, line in enumerate(lines):

            line_width = line_data[index]["width"]

            if overlay_position in {
                "top-center",
                "center",
                "bottom-center",
            }:
                x = (width - line_width) // 2

            elif overlay_position in {
                "top-right",
                "center-right",
                "bottom-right",
            }:
                x = width - line_width - margin

            else:
                x = margin

            # Keep X inside image
            x = max(
                margin,
                min(
                    x,
                    width - line_width - margin,
                ),
            )

            # Black outline
            cv2.putText(
                image,
                line,
                (x, current_y),
                font,
                font_scale,
                (0, 0, 0),
                outline_thickness,
                cv2.LINE_AA,
            )

            # White text
            cv2.putText(
                image,
                line,
                (x, current_y),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

            current_y += (
                line_data[index]["height"]
                + line_data[index]["baseline"]
                + line_spacing
            )

        # ---------------------------------------------------------
        # ENCODE IMAGE
        # ---------------------------------------------------------

        success, encoded_image = cv2.imencode(
            ".jpg",
            image,
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )

        if not success:
            logger.error(
                "Failed to encode image after applying overlay text"
            )
            return image_bytes

        logger.info(
            "Custom overlay text successfully applied | "
            "position=%s | text_size=%s | lines=%s",
            overlay_position,
            text_size,
            len(lines),
        )

        return encoded_image.tobytes()

    except Exception:
        logger.exception(
            "Failed to apply custom overlay text with OpenCV"
        )
        return image_bytes

async def apply_footer_with_opencv(
    image_bytes: bytes,
    footer_url: str | None,
) -> bytes | None:
    """
    Add the user's footer as a full-width banner
    across the bottom of the generated image.
    """

    if not footer_url:
        logger.info(
            "No footer URL configured; skipping footer overlay"
        )
        return image_bytes

    try:
        # ---------------------------------------------------------
        # 1. Download footer
        # ---------------------------------------------------------
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(footer_url)
            response.raise_for_status()
            footer_bytes = response.content

        # ---------------------------------------------------------
        # 2. Decode generated image
        # ---------------------------------------------------------
        base_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        base_image = cv2.imdecode(
            base_array,
            cv2.IMREAD_COLOR,
        )

        if base_image is None:
            logger.error(
                "Unable to decode generated image for footer"
            )
            return None

        # ---------------------------------------------------------
        # 3. Decode footer
        # ---------------------------------------------------------
        footer_array = np.frombuffer(
            footer_bytes,
            dtype=np.uint8,
        )

        footer = cv2.imdecode(
            footer_array,
            cv2.IMREAD_UNCHANGED,
        )

        if footer is None:
            logger.error(
                "Unable to decode footer image"
            )
            return None

        base_height, base_width = base_image.shape[:2]

        footer_height, footer_width = footer.shape[:2]

        if footer_width <= 0 or footer_height <= 0:
            logger.error(
                "Footer image has invalid dimensions"
            )
            return None

        # ---------------------------------------------------------
        # 4. FULL WIDTH footer
        # ---------------------------------------------------------
        target_width = base_width

        scale = target_width / footer_width

        target_height = max(
            1,
            int(footer_height * scale),
        )

        footer = cv2.resize(
            footer,
            (
                target_width,
                target_height,
            ),
            interpolation=cv2.INTER_AREA,
        )

        # ---------------------------------------------------------
        # 5. Put footer across the bottom
        # ---------------------------------------------------------
        x1 = 0
        y1 = base_height - target_height

        x2 = base_width
        y2 = base_height

        # ---------------------------------------------------------
        # 6. If footer is transparent
        # ---------------------------------------------------------
        if footer.ndim == 3 and footer.shape[2] == 4:

            footer_rgb = footer[:, :, :3]

            alpha = (
                footer[:, :, 3]
                .astype(np.float32)
                / 255.0
            )

            background = base_image[
                y1:y2,
                x1:x2
            ].astype(np.float32)

            foreground = footer_rgb.astype(
                np.float32
            )

            alpha = alpha[:, :, np.newaxis]

            blended = (
                foreground * alpha
                +
                background * (1.0 - alpha)
            )

            base_image[
                y1:y2,
                x1:x2
            ] = np.clip(
                blended,
                0,
                255,
            ).astype(np.uint8)

        # ---------------------------------------------------------
        # 7. Normal JPG/PNG footer
        # ---------------------------------------------------------
        else:

            base_image[
                y1:y2,
                x1:x2
            ] = footer[:, :, :3]

        # ---------------------------------------------------------
        # 8. Encode final image
        # ---------------------------------------------------------
        success, encoded = cv2.imencode(
            ".jpg",
            base_image,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                95,
            ],
        )

        if not success:
            logger.error(
                "Failed to encode image after footer overlay"
            )
            return None

        logger.info(
            "Footer successfully applied | "
            "position=full-width-bottom | "
            "width=%s | height=%s",
            target_width,
            target_height,
        )

        return encoded.tobytes()

    except Exception:
        logger.exception(
            "Failed to apply footer with OpenCV"
        )
        return None
  
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

    if has_fresh_events_cache(country_code):
        return get_cached_events(country_code)

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

            delete_events_cache(country_code)

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

                save_event(
                    country_code=country_code,
                    event_name=h.get("name"),
                    event_date=event_date,
                    event_type=event_type,
                    raw_data=h
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

    return get_cached_events(country_code)

# ============================================================
# GOOGLE NEWS TRENDS
# ============================================================

def fetch_google_trends(country_code: str, industry: str) -> list:

    if has_fresh_trends_cache(
        country_code=country_code,
        platform="google_news",
        hours=6,
    ):
        return get_cached_trends(
            country_code=country_code,
            platform="google_news",
            hours=6,
        )

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

    delete_trends_cache(
        platform="google_news",
        country_code=country_code,
    )

    for i, topic in enumerate(topics[:15]):

        save_trend(
            country_code=country_code,
            platform="google_news",
            topic=topic,
            score=15 - i,
        )

    logger.info(
        "Google News trends fetched for %s",
        country_code
    )

    return get_cached_trends(
        country_code=country_code,
        platform="google_news",
    )
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

    profile = get_rag_profile(user_id) or {}

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

    recent_posts = get_recent_posts_for_rag(user_id, limit=8)

    for post in recent_posts:
        platforms = post.get("platforms") or []

        if isinstance(platforms, str):
            platforms = [platforms]
        elif isinstance(platforms, list):
            flattened_platforms = []

            for platform in platforms:
                if isinstance(platform, list):
                    flattened_platforms.extend(platform)
                elif isinstance(platform, str):
                    flattened_platforms.append(platform)

            platforms = flattened_platforms

        docs.append(
            {
                "source": "Recent post",
                "title": post.get("created_at", "Recent post"),
                "content": (
                    f"Content: {post.get('content_text', '')}\n"
                    f"Platforms: {', '.join(platforms)}"
                )
            }
        )

    country_code = profile.get("country_code") if profile else None

    if country_code:
        events = get_events_for_rag(country_code, limit=8)

        for event in events:
            docs.append(
                {
                    "source": "Upcoming event",
                    "title": event.get("event_name", "Event"),
                    "content": (
                        f"Event: {event.get('event_name', '')}\n"
                        f"Date: {event.get('event_date', '')}\n"
                        f"Type: {event.get('event_type', '')}"
                    )
                }
            )

        trends = get_trends_for_rag(country_code, limit=8)

        for trend in trends:
            docs.append(
                {
                    "source": "Trending topic",
                    "title": trend.get("topic", "Trend"),
                    "content": f"Topic: {trend.get('topic', '')}"
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
    return get_chat_history(user_id=user_id, limit=limit)


def _save_chat_turn(
    user_id: int,
    role: str,
    content: str
):
    return save_chat_turn(
        user_id=user_id,
        role=role,
        content=content,
    )

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
            "Raw title-based LLM response: %r",
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
            timeout=120.0
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
        profile,
    )

    if not image_bytes:
        return None

    # -----------------------------
    # Company logo
    # -----------------------------

    logo_url = profile.get("logo_url")

    image_bytes = await apply_logo_with_opencv(
        image_bytes=image_bytes,
        logo_url=logo_url,
    )

    if not image_bytes:
        logger.warning(
            "Logo branding failed; generated image will not be uploaded"
        )
        return None

    # -----------------------------
    # Custom overlay text
    # -----------------------------
    overlay_text = profile.get("overlay_text")
    overlay_position = profile.get(
        "overlay_position",
        "bottom-center",
    )
    overlay_text_size = profile.get(
    "overlay_text_size",
    48,
      )

    logger.info(
        "Overlay text data | text_present=%s | position=%s",
        bool(overlay_text),
        overlay_position,
    )

    if overlay_text:
        image_bytes = await apply_overlay_text_with_opencv(
            image_bytes=image_bytes,
            overlay_text=overlay_text,
            overlay_position=overlay_position,
            overlay_text_size=overlay_text_size,
        )

        if not image_bytes:
            logger.warning(
                "Overlay text branding failed; generated image will not be uploaded"
            )
            return None


    # -----------------------------
    # Company footer
    # -----------------------------

    footer_enabled = profile.get(
        "footer_enabled",
        False,
    )

    footer_url = profile.get(
        "footer_url",
    )

    if footer_enabled and footer_url:
        image_bytes = await apply_footer_with_opencv(
            image_bytes=image_bytes,
            footer_url=footer_url,
        )

        if not image_bytes:
            logger.warning(
                "Footer branding failed; generated image will not be uploaded"
            )
            return None

    else:
        logger.info(
            "Footer branding skipped | enabled=%s | has_url=%s",
            footer_enabled,
            bool(footer_url),
        )

    return upload_generated_image(image_bytes)

   


# ============================================================
# REDDIT TRENDS
# ============================================================

async def fetch_reddit_trends(
    industry: str,
    country_code: str
) -> list:

    if has_fresh_trends_cache(
        country_code=country_code,
        platform="reddit",
        hours=3,
    ):
        return get_cached_trends(
            country_code=country_code,
            platform="reddit",
            hours=3,
        )

    INDUSTRY_SUBREDDITS = {
        "tech": ["technology", "programming", "artificial"],
        "marketing": ["marketing", "socialmedia", "digital_marketing"],
        "finance": ["investing", "personalfinance", "entrepreneur"],
        "health": ["health", "fitness", "nutrition"],
        "education": ["education", "learnprogramming", "Teachers"],
        "ecommerce": ["ecommerce", "entrepreneur", "smallbusiness"],
        "design": ["design", "graphic_design", "UI_Design"],
        "saas": ["SaaS", "startups", "entrepreneur"],
    }

    keyword = (industry or "").split(",")[0].strip().lower()
    subreddits = INDUSTRY_SUBREDDITS.get(
        keyword,
        ["technology", "business"],
    )

    topics = []

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "socialdesk-trends/1.0"},
        ) as client:
            for sub in subreddits[:2]:
                resp = await client.get(
                    f"https://www.reddit.com/r/{sub}/hot.json",
                    params={"limit": 5},
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
                    score = post.get("data", {}).get("score", 0)

                    if title and title not in [t[0] for t in topics]:
                        topics.append((title, score))

    except Exception:
        logger.exception("Reddit trend fetch failed")
        return []

    if not topics:
        return []

    delete_trends_cache(
        platform="reddit",
        country_code=country_code,
    )

    for title, score in topics[:10]:
        save_trend(
            country_code=country_code,
            platform="reddit",
            topic=title,
            score=score,
        )

    logger.info("Reddit trends fetched for %s", country_code)

    return get_cached_trends(
        country_code=country_code,
        platform="reddit",
    )

async def fetch_hackernews_trends() -> list:

    if has_fresh_trends_cache(
        country_code=None,
        platform="hackernews",
        hours=3,
    ):
        return get_cached_trends(
            country_code=None,
            platform="hackernews",
            hours=3,
        )

    topics = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
                return_exceptions=True,
            )

            for response in story_resps:
                if isinstance(response, Exception):
                    continue

                story = response.json()
                title = story.get("title", "").strip()
                score = story.get("score", 0)

                if title:
                    topics.append((title, score))

    except Exception:
        logger.exception("HackerNews fetch failed")
        return []

    if not topics:
        return []

    delete_trends_cache(platform="hackernews")

    for title, score in topics[:10]:
        save_trend(
            country_code="GLOBAL",
            platform="hackernews",
            topic=title,
            score=score,
        )

    logger.info("HackerNews trends fetched")

    return get_cached_trends(
        country_code=None,
        platform="hackernews",
    )

async def fetch_producthunt_trends() -> list:

    if has_fresh_trends_cache(
        country_code=None,
        platform="producthunt",
        hours=6,
    ):
        return get_cached_trends(
            country_code=None,
            platform="producthunt",
            hours=6,
        )

    topics = []

    try:
        feed = feedparser.parse("https://www.producthunt.com/feed")

        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            if title:
                topics.append(title)

    except Exception:
        logger.exception("ProductHunt fetch failed")
        return []

    if not topics:
        return []

    delete_trends_cache(platform="producthunt")

    for i, title in enumerate(topics[:10]):
        save_trend(
            country_code="GLOBAL",
            platform="producthunt",
            topic=title,
            score=10 - i,
        )

    logger.info("ProductHunt trends fetched")

    return get_cached_trends(
        country_code=None,
        platform="producthunt",
    )

async def fetch_github_trending(
    industry: str
) -> list:

    if has_fresh_trends_cache(
        country_code=None,
        platform="github",
        hours=6,
    ):
        return get_cached_trends(
            country_code=None,
            platform="github",
            hours=6,
        )

    LANGUAGE_MAP = {
        "tech": "python",
        "saas": "javascript",
        "design": "css",
        "data": "jupyter-notebook",
        "mobile": "swift",
    }

    keyword = (industry or "").split(",")[0].strip().lower()
    language = LANGUAGE_MAP.get(keyword, "")
    topics = []

    try:
        url = f"https://github.com/trending/{language}?since=daily"

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; socialdesk/1.0)"
                )
            },
        ) as client:
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning(
                    "GitHub trending returned %s",
                    resp.status_code,
                )
                return []

            matches = _re.findall(
                r'href="/([^/"]+/[^/"]+)"[^>]*>\s*\n\s*<span',
                resp.text,
            )

            seen = set()
            for repo in matches:
                if repo in seen:
                    continue

                seen.add(repo)
                topics.append(repo)

                if len(topics) >= 10:
                    break

    except Exception:
        logger.exception("GitHub trending fetch failed")
        return []

    if not topics:
        return []

    delete_trends_cache(platform="github")

    for i, repo in enumerate(topics[:10]):
        save_trend(
            country_code="GLOBAL",
            platform="github",
            topic=repo,
            score=10 - i,
        )

    logger.info("GitHub trending fetched")

    return get_cached_trends(
        country_code=None,
        platform="github",
    )

async def run_recommendation_pipeline(
    user_id: int
) -> list:

    profile = get_user_profile(user_id)

    if not profile:
        logger.warning(
            "No profile for user %s, skipping",
            user_id,
        )
        return []

    country_code = profile.get("country_code", "IN")
    industry = profile.get("industry", "business")

    platforms = get_connected_platforms(user_id)
    if not platforms:
        platforms = ["linkedin"]

    logger.info(
        "Platforms configured for user %s: %s",
        user_id,
        platforms,
    )

    (
        events,
        google_trends,
        reddit_trends,
        hn_trends,
        ph_trends,
        gh_trends,
    ) = await asyncio.gather(
        fetch_holidays(country_code),
        asyncio.to_thread(
            fetch_google_trends,
            country_code,
            industry,
        ),
        fetch_reddit_trends(industry, country_code),
        fetch_hackernews_trends(),
        fetch_producthunt_trends(),
        fetch_github_trending(industry),
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
        profile,
    )

    generated_posts = []
    days_offset = 0

    for event in relevant.get("relevant_events", []):
        if has_duplicate_post_for_trigger(
            user_id=user_id,
            trigger_name=event["event_name"],
        ):
            logger.info(
                "Skipping duplicate event post: %s",
                event["event_name"],
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
                "angle": event["angle"],
            },
            platform=primary_platform,
        )

        if not content.get("caption"):
            continue

        media_url = await generate_media_url(
            content.get("image_prompt", ""),
            profile,
        )

        post_platforms = list(platforms)

        if not media_url and "instagram" in post_platforms:
            logger.info(
                "No image generated; dropping Instagram for event post: %s",
                event["event_name"],
            )
            post_platforms = [
                platform
                for platform in post_platforms
                if platform != "instagram"
            ]

        try:
            event_date = datetime.strptime(
                str(event["event_date"]),
                "%Y-%m-%d",
            )
            scheduled_at = event_date - timedelta(days=3)
            scheduled_at = scheduled_at.replace(
                hour=9,
                minute=0,
                second=0,
                tzinfo=timezone.utc,
            )

            if scheduled_at < datetime.now(timezone.utc):
                scheduled_at = (
                    datetime.now(timezone.utc)
                    + timedelta(days=1)
                ).replace(
                    hour=9,
                    minute=0,
                    second=0,
                )

        except Exception:
            scheduled_at = (
                datetime.now(timezone.utc)
                + timedelta(days=days_offset + 1)
            )

        generated_posts.append(
            {
                "content_text": content["caption"],
                "platforms": post_platforms,
                "scheduled_at": scheduled_at,
                "trigger_type": "event",
                "trigger_name": event["event_name"],
                "media_url": media_url,
            }
        )

        days_offset += 2

    for trend in relevant.get("relevant_trends", []):
        if has_duplicate_post_for_trigger(
            user_id=user_id,
            trigger_name=trend["topic"],
        ):
            logger.info(
                "Skipping duplicate trend post: %s",
                trend["topic"],
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
                "angle": trend["angle"],
            },
            platform=primary_platform,
        )

        if not content.get("caption"):
            continue

        media_url = await generate_media_url(
            content.get("image_prompt", ""),
            profile,
        )

        post_platforms = list(platforms)

        if not media_url and "instagram" in post_platforms:
            logger.info(
                "No image generated; dropping Instagram for trend post: %s",
                trend["topic"],
            )
            post_platforms = [
                platform
                for platform in post_platforms
                if platform != "instagram"
            ]

        scheduled_at = (
            datetime.now(timezone.utc)
            + timedelta(days=days_offset + 1)
        ).replace(
            hour=9,
            minute=0,
            second=0,
        )

        generated_posts.append(
            {
                "content_text": content["caption"],
                "platforms": post_platforms,
                "scheduled_at": scheduled_at,
                "trigger_type": "trend",
                "trigger_name": trend["topic"],
                "media_url": media_url,
            }
        )

        days_offset += 2

    logger.info(
        "Generated %s posts for user %s",
        len(generated_posts),
        user_id,
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