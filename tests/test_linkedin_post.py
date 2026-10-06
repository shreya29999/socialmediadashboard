import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")

# Your Cloudinary image URL
IMAGE_URL = (
    "https://res.cloudinary.com/hoxls2zu/image/upload/"
    "v1791199426/socialdesk/ai_generated/"
    "psvxap64ioggjuvz75ef.jpg"
)

CAPTION = (
    "🚀 Testing SocialDesk LinkedIn integration.\n\n"
    "This is a test post published automatically "
    "through the LinkedIn API."
)

LINKEDIN_VERSION = "202610"


# ============================================================
# VALIDATE CONFIG
# ============================================================

if not LINKEDIN_ACCESS_TOKEN:
    print("❌ LINKEDIN_ACCESS_TOKEN is missing from .env")
    sys.exit(1)


HEADERS = {
    "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
    "Linkedin-Version": LINKEDIN_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
    "Content-Type": "application/json",
}


# ============================================================
# STEP 1 — GET LINKEDIN PROFILE
# ============================================================

def get_linkedin_profile():
    print("\n1️⃣ Getting LinkedIn profile...")

    response = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"
        },
        timeout=30,
    )

    print("Status:", response.status_code)

    try:
        data = response.json()
    except ValueError:
        print(response.text)
        return None

    if response.status_code != 200:
        print("❌ Failed to get LinkedIn profile")
        print(data)
        return None

    print("✅ LinkedIn profile retrieved")
    print("Name:", data.get("name"))
    print("Email:", data.get("email"))
    print("Sub:", data.get("sub"))

    linkedin_sub = data.get("sub")

    if not linkedin_sub:
        print("❌ LinkedIn member ID is missing")
        return None

    user_urn = f"urn:li:person:{linkedin_sub}"

    print("Member URN:", user_urn)

    return user_urn


# ============================================================
# STEP 2 — INITIALIZE IMAGE UPLOAD
# ============================================================

def initialize_image_upload(user_urn):
    print("\n2️⃣ Initializing LinkedIn image upload...")

    payload = {
        "initializeUploadRequest": {
            "owner": user_urn
        }
    }

    response = httpx.post(
        "https://api.linkedin.com/rest/images?action=initializeUpload",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )

    print("Status:", response.status_code)

    try:
        data = response.json()
    except ValueError:
        print(response.text)
        return None, None

    print("Response:", data)

    if response.status_code not in (200, 201):
        print("❌ LinkedIn image initialization failed")
        return None, None

    value = data.get("value", {})

    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")

    if not upload_url:
        print("❌ LinkedIn did not return uploadUrl")
        return None, None

    if not image_urn:
        print("❌ LinkedIn did not return image URN")
        return None, None

    print("✅ Image upload initialized")
    print("Image URN:", image_urn)

    return upload_url, image_urn


# ============================================================
# STEP 3 — DOWNLOAD IMAGE FROM CLOUDINARY
# ============================================================

def download_image():
    print("\n3️⃣ Downloading image from Cloudinary...")

    response = httpx.get(
        IMAGE_URL,
        timeout=30,
    )

    print("Status:", response.status_code)

    if response.status_code != 200:
        print("❌ Could not download image")
        print(response.text)
        return None, None

    content_type = response.headers.get(
        "content-type",
        "image/jpeg",
    )

    print("✅ Image downloaded")
    print("Content-Type:", content_type)
    print("Image size:", len(response.content), "bytes")

    return response.content, content_type


# ============================================================
# STEP 4 — UPLOAD IMAGE TO LINKEDIN
# ============================================================

def upload_image(upload_url, image_bytes, content_type):
    print("\n4️⃣ Uploading image to LinkedIn...")

    response = httpx.put(
        upload_url,
        content=image_bytes,
        headers={
            "Content-Type": content_type,
        },
        timeout=60,
    )

    print("Status:", response.status_code)

    if response.status_code not in (200, 201, 202):
        print("❌ LinkedIn image upload failed")
        print(response.text)
        return False

    print("✅ Image uploaded successfully")

    return True


# ============================================================
# STEP 5 — CREATE LINKEDIN POST
# ============================================================

def create_linkedin_post(user_urn, image_urn):
    print("\n5️⃣ Creating LinkedIn post...")

    payload = {
        "author": user_urn,
        "commentary": CAPTION,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "altText": "SocialDesk LinkedIn API test image",
                "id": image_urn,
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    response = httpx.post(
        "https://api.linkedin.com/rest/posts",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )

    print("Status:", response.status_code)

    try:
        data = response.json()
    except ValueError:
        data = response.text

    print("Response:", data)

    if response.status_code != 201:
        print("❌ LinkedIn post creation failed")
        return False

    post_id = response.headers.get("x-restli-id")

    print("\n========================================")
    print("✅ LINKEDIN POST PUBLISHED SUCCESSFULLY")
    print("========================================")
    print("Post ID:", post_id)
    print("Image:", image_urn)
    print("========================================")

    return True


# ============================================================
# MAIN TEST
# ============================================================

def main():
    print("========================================")
    print(" SOCIALDESK LINKEDIN IMAGE TEST")
    print("========================================")

    # 1. Get LinkedIn member URN
    user_urn = get_linkedin_profile()

    if not user_urn:
        return

    # 2. Initialize LinkedIn image upload
    upload_url, image_urn = initialize_image_upload(
        user_urn
    )

    if not upload_url or not image_urn:
        return

    # 3. Download image
    image_bytes, content_type = download_image()

    if not image_bytes:
        return

    # 4. Upload image
    uploaded = upload_image(
        upload_url,
        image_bytes,
        content_type,
    )

    if not uploaded:
        return

    # 5. Create LinkedIn post
    create_linkedin_post(
        user_urn,
        image_urn,
    )


if __name__ == "__main__":
    main()