from time import time

from openai import OpenAI
from loguru import logger


def recognize_text_in_image(openai_client: OpenAI, img_str: str) -> str | None:
    start = time()

    completion = openai_client.chat.completions.create(
        # extra_headers={
        #     "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        #     "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
        # },
        extra_body={"reasoning": {"enabled": False}},
        # model="allenai/molmo-2-8b:free",
        # model="openai/gpt-5.2",
        model="openai/gpt-4.1-mini",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Recognize text in image and output the text."
                            "Do not output anything other than the recognized text. "
                            # "Translate the text to English if it is in another language. "
                            "If there is no recognizable text, output \"NO_TEXT\". "
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_str
                    }
                },
            ]
        }]
    )

    logger.debug(f"Image processed in {time() - start:.2f} s")

    try:
        text = completion.choices[0].message.content
        logger.debug(f"Text: {text}")

        if text is None or text.strip().upper() == "NO_TEXT":
            return None
        else:
            return text.strip()
    except (IndexError, AttributeError):
        return None
