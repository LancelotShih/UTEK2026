import tomllib
from pathlib import Path

import sounddevice as sd
from openai import OpenAI
import numpy as np
from loguru import logger

from tts import TTSAPIClient
from esp_cam import CameraClient
from recognize import recognize_text_in_image


CONFIG_PATH = Path(__file__).parent / "config.toml"
TEST_IMG_PATH = Path(__file__).parent / "test/ocr_test_1.webp"


class State:
    openai_client: OpenAI
    camera_client: CameraClient
    tts_client: TTSAPIClient

    memory: list[str] = []

    def __init__(self, path: Path):
        # Load config
        data = tomllib.loads(path.read_text())

        # Init drivers
        self.openai_client = OpenAI(
            base_url=data["base_urls"]["openrouter"],
            api_key=data["keys"]["openrouter"],
        )

        self.camera_client = CameraClient(
            base_url=data["base_urls"]["esp"]
        )

        self.tts_client = TTSAPIClient(
            api_url=data["base_urls"]["tts"],
            api_key=data["keys"]["google"],
        )

        self.memory = []

        logger.info("State initialized")

    def add_to_memory(self, words: list[str]):
        self.memory.extend(words)
        while len(self.memory) > 30:
            self.memory.pop(0)
        logger.debug(f"Memory: {', '.join(self.memory)}")


def ocr(speed: float = 1.0) -> tuple[np.ndarray, list[str]] | None:
    """Takes picture and returns tuple of speech audio (int16 numpy array, 24000 Hz) and list of words."""

    img_str = state.camera_client.capture_b64(flash=True, show=False)
    if img_str is None:
        logger.error("Failed to capture image from camera")
        return None

    text = recognize_text_in_image(state.openai_client, img_str)
    if text is None:
        logger.info("No text recognized in image")
        return None
    state.add_to_memory(text.split())

    speech = state.tts_client.get_tts(text, speed=speed)
    if speech is None:
        logger.error("Failed to get text-to-speech audio from text")
        return None

    sd.play(speech, samplerate=24000, blocking=True)
    return speech, text.split()


def repeat(speed: float = 1.0) -> tuple[np.ndarray, list[str]] | None:
    """Repeats the words in memory, returned as speech audio (int16 numpy array, 24000 Hz) and list of words."""

    if len(state.memory) == 0:
        text = "Memory is empty."
    else:
        text = " ".join(state.memory)

    speech = state.tts_client.get_tts(text, speed=speed)
    if speech is None:
        logger.error("Failed to get text-to-speech audio from text")
        return None

    sd.play(speech, samplerate=24000, blocking=True)
    return speech, state.memory


if __name__ == "__main__":
    global state
    state = State(CONFIG_PATH)
    # config = tomllib.loads(CONFIG_PATH.read_text())
    # global tts_client
    # tts_client = TTSAPIClient(
    #     api_url=config["base_urls"]["tts"],
    #     api_key=config["keys"]["google"],
    # )
    # api_key = config["keys"]["openrouter"]
    # esp_url = config["base_urls"]["esp"]

    while True:
        mode = input("enter for capture, r for repeat: ")
        if mode == "r":
            repeat()
        else:
            ocr()
