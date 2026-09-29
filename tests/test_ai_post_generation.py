import asyncio

from app.ai.event_fetcher import (
    generate_media_url,
    generate_post_content_from_title,
)


PROFILE = {
    "persona": "Technology Solutions Company",
    "industry": "Software Development and IT Services",
    "brand_name": "Shilsha Technologies",
    "tone": "Professional, innovative, informative, and approachable",
    "audience": (
        "Businesses, startups, technology leaders, developers, "
        "and organizations looking for software and digital solutions"
    ),
}

async def main():
    print("\n" + "=" * 70)
    print("       SOCIALDESK AI POST + IMAGE GENERATION DEMO")
    print("=" * 70)

    # ---------------------------------------------------------
    # USER INPUT
    # ---------------------------------------------------------

    title = input("\nEnter the topic/title: ").strip()

    if not title:
        print("[FAILED] Topic/title is required.")
        return

    print(f"\nUser Input: {title}")

    # ---------------------------------------------------------
    # STEP 1 - GROQ GENERATES CAPTION + IMAGE PROMPT
    # ---------------------------------------------------------

    print("\n[1/2] Generating caption and image prompt with Groq...")

    post = generate_post_content_from_title(
        profile=PROFILE,
        title=title,
        platform="linkedin",
    )

    caption = post.get("caption", "").strip()
    image_prompt = post.get("image_prompt", "").strip()

    if not caption:
        print("[FAILED] Caption generation failed.")
        return

    if not image_prompt:
        print("[FAILED] Image prompt generation failed.")
        return

    print("\n[SUCCESS] AI content generated.")

    print("\n--- GENERATED CAPTION ---")
    print(caption)

    print("\n--- GENERATED IMAGE PROMPT ---")
    print(image_prompt)

    # ---------------------------------------------------------
    # STEP 2 - POLLINATIONS + CLOUDINARY
    # ---------------------------------------------------------

    print("\n[2/2] Generating image and uploading to Cloudinary...")

    url = await generate_media_url(
        image_prompt=image_prompt,
        profile=PROFILE,
    )

    if not url:
        print("[FAILED] Image generation or Cloudinary upload failed.")
        return

    print("\n[SUCCESS] Image generated and uploaded!")

    print("\n--- CLOUDINARY URL ---")
    print(url)

    # ---------------------------------------------------------
    # FINAL
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("                 DEMO COMPLETED")
    print("=" * 70)

    print("\nFlow:")
    print("User Input")
    print("    ↓")
    print("Groq")
    print("    ↓")
    print("Caption + Image Prompt")
    print("    ↓")
    print("Pollinations")
    print("    ↓")
    print("AI Image")
    print("    ↓")
    print("Cloudinary")
    print("    ↓")
    print("Cloudinary URL")


if __name__ == "__main__":
    asyncio.run(main())