
import requests
import base64
import io


class TTSAPIClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def get_tts(self, input: str, speed: float = 0.75) -> io.BytesIO:
        payload = {
            "input": {
                "text": input,
            },
            "voice": {
                "languageCode": "en-US",
                "name": "en-US-Standard-F",
            },
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "speakingRate": speed
            },
        }

        resp = requests.post(f"{self.api_url}?key={self.api_key}", json=payload)

        if not resp.ok:
            print(f"get_tts({input}, {speed}) response not OK: code {resp.status_code} {resp.text}")
            return None

        data = resp.json()
        wav_bytes = base64.urlsafe_b64decode(data["audioContent"])

        return io.BytesIO(wav_bytes)
