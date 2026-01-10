from io import BytesIO
import base64
import tomllib
from pathlib import Path
from time import time, sleep

import requests
import sounddevice as sd
from PIL import Image, ImageOps
from openai import OpenAI
import numpy as np

from tts import TTSAPIClient


CONFIG_PATH = Path(__file__).parent / "config.toml"
TEST_IMG_PATH = Path(__file__).parent / "test/ocr_test_1.webp"


def quickstart(key: str, img_url: str):
    # jpeg_buf = BytesIO()
    # img = Image.open(TEST_IMG_PATH).save(jpeg_buf, format="JPEG")
    # img_raw_b64 = base64.b64encode(jpeg_buf.getvalue())

    start = time()
    requests.get(img_url + "/flash")
    sleep(0.15)
    resp = requests.get(img_url + "/capture")
    sleep(0.15)
    requests.get(img_url + "/flash")
    print(f"Image downloaded in {(time() - start)*1000:.2f} ms")

    start = time()
    img_raw_b64 = base64.b64encode(resp.content)
    img_str = f"data:image/jpeg;base64,{img_raw_b64.decode()}"
    print(f"Image b64 encoded in {(time() - start)*1000:.2f} ms")

    im = Image.open(BytesIO(resp.content), formats=["JPEG"])
    im.show()
    # flipped = ImageOps.flip(im)
    # flipped.show()

    start = time()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
    )

    completion = client.chat.completions.create(
        # extra_headers={
        #     "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        #     "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
        # },
        extra_body={"reasoning": {"enabled": True}},
        # model="allenai/molmo-2-8b:free",
        # model="openai/gpt-5.2",
        model="openai/gpt-4.1-mini",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Recognize text in image and output: \"CONFIDENCE: <confidence score>\nTEXT: <recognized text>"
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

    text = completion.choices[0].message.content
    # text = "testing"
    print(text)
    print(f"Image processed in {time() - start:.2f} s")

    if text is not None:
        start = time()
        speech = tts_client.get_tts(text, speed=1.5)
        speech_np = np.frombuffer(speech.read(), dtype=np.int16)
        print(f"Got TTS in {time() - start:.2f} s")
        sd.play(speech_np, samplerate=24000, blocking=True)


if __name__ == "__main__":
    config = tomllib.loads(CONFIG_PATH.read_text())
    global tts_client
    tts_client = TTSAPIClient(
        api_url=config["base_urls"]["tts"],
        api_key=config["keys"]["google"],
    )
    api_key = config["keys"]["openrouter"]
    esp_url = config["base_urls"]["esp"]
    quickstart(api_key, esp_url)
