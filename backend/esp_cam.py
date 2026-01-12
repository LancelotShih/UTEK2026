import base64
from io import BytesIO
from time import time, sleep

import requests
from PIL import Image
from loguru import logger


class CameraClient:
    base_url: str
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        # TODO: verify connection by GET /

    def _get(self, url: str, timeout: float = 1.0) -> requests.Response | None:
        try:
            return requests.get(url, timeout=timeout)
        except requests.exceptions.Timeout:
            logger.error(f"HTTP GET timed out after {timeout} s")
            return None
    
    def capture_raw(self, flash: bool = True) -> bytes | None:
        start = time()

        if flash:
            self._get(self.base_url + "/flash")
            sleep(0.15)

        resp = self._get(self.base_url + "/capture", timeout=5.0)
    
        if flash:
            self._get(self.base_url + "/flash")

        logger.debug(f"Image downloaded in {(time() - start)*1000:.2f} ms")
        return resp.content if resp is not None else None

    def capture_b64(self, flash: bool = True, show: bool = False) -> str | None:
        raw = self.capture_raw(flash=flash)
        if raw is None:
            return None
        
        if show:
            im = Image.open(BytesIO(raw), formats=["JPEG"])
            im.show()
        
        start = time()

        img_raw_b64 = base64.b64encode(raw)
        img_str = f"data:image/jpeg;base64,{img_raw_b64.decode()}"
        logger.debug(f"Image b64 encoded in {(time() - start)*1000:.2f} ms")

        return img_str
