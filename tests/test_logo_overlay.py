import asyncio
import logging

import cv2
import numpy as np

from app.ai.event_fetcher import apply_logo_with_opencv


logging.basicConfig(level=logging.INFO)


LOGO_URL = (
    "https://res.cloudinary.com/hoxls2zu/image/upload/"
    "v1790837451/socialdesk/logos/b1bvi4yomza33xr1kl6a.jpg"
)


async def main():
    # Create a temporary 1080x1080 test image
    test_image = np.full(
        (1080, 1080, 3),
        240,
        dtype=np.uint8,
    )

    success, encoded_image = cv2.imencode(
        ".jpg",
        test_image,
    )

    if not success:
        logging.error("Failed to create test image")
        return

    image_bytes = encoded_image.tobytes()

    # Apply company logo
    branded_image = await apply_logo_with_opencv(
        image_bytes=image_bytes,
        logo_url=LOGO_URL,
    )

    if not branded_image:
        logging.error("Logo overlay test failed")
        return

    # Save result locally for visual inspection
    with open("test_output.jpg", "wb") as file:
        file.write(branded_image)

    logging.info("Logo overlay test successful")
    logging.info("Output: test_output.jpg")


if __name__ == "__main__":
    asyncio.run(main())