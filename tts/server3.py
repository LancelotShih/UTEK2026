"""
Run:
  pip install "uvicorn[standard]" fastapi numpy
  uvicorn server:app --reload --host 0.0.0.0 --port 8000
Open:
  http://127.0.0.1:8000/
"""

from __future__ import annotations

import asyncio
import math
import struct
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

MIN_TIME = 0.12



# -----------------------------
# Audio config + generator
# -----------------------------

@dataclass(frozen=True)
class AudioConfig:
    sample_rate_hz: int = 16_000
    channels: int = 1 #mono audio
    chunk_ms: int = 100

    @property
    def chunk_samples(self) -> int:
        return self.sample_rate_hz * self.chunk_ms // 1000

    @property
    def chunk_duration_sec(self) -> float:
        return self.chunk_samples / self.sample_rate_hz

    @property
    def chunk_bytes(self) -> int:
        return self.chunk_samples * self.channels * 2  # int16


AUDIO = AudioConfig()


def _clamp_int16(x: float) -> int:
    x = max(-1.0, min(1.0, x))
    return int(x * 32767)


# -----------------------------
# Example OCR / repeat hooks
# -----------------------------

def _tone(freq_hz: float, duration_sec: float, amp: float = 0.4) -> np.ndarray:
    t = np.linspace(0, duration_sec, int(AUDIO.sample_rate_hz * duration_sec), endpoint=False)
    wave = amp * np.sin(2 * math.pi * freq_hz * t)
    return np.array([_clamp_int16(x) for x in wave], dtype=np.int16)


def OCR() -> Tuple[np.ndarray, List[str]]:
    # 3 short beeps: low → mid → high
    audio = np.concatenate([
        _tone(440, 0.25),
        _tone(660, 0.25),
        _tone(880, 0.25),
    ])
    words = ["hello", "from", "ocr", "hello", "from", "ocr", "hello", "from", "ocr"]
    return audio, words


def repeat() -> Tuple[np.ndarray, List[str]]:
    # 2 longer beeps
    audio = np.concatenate([
        _tone(330, 0.4),
        _tone(330, 0.4),
    ])
    words = ["repeat", "mode"]
    return audio, words


def ndarray_to_linear16_bytes(audio_np: np.ndarray) -> bytes:
    if audio_np.dtype == np.uint8:
        return audio_np.tobytes(order="C")

    if audio_np.dtype == np.int16:
        a = np.ascontiguousarray(audio_np)
        if a.dtype.byteorder == ">":
            a = a.byteswap().newbyteorder()
        return a.tobytes(order="C")

    raise TypeError("Unsupported numpy dtype for LINEAR16")


# -----------------------------
# Minimal website
# -----------------------------


INDEX_HTML_MIN = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PCM Stream Test</title>
    <style>
    body {{
        font-family: Arial, Helvetica, sans-serif;
        max-width: 900px;
        margin: 40px auto;
        padding: 0 24px;
        font-size: 24px;
        line-height: 1.7;
    }}

    h2 {{
        font-size: 40px;
        margin-bottom: 28px;
    }}

    button {{
        padding: 32px 44px;
        font-size: 36px;
        font-weight: 700;
        cursor: pointer;
        margin-right: 20px;
        margin-bottom: 20px;
        border-radius: 18px;
        border: 3px solid #000;
        background: #ffffff;
    }}

    button:focus {{
        outline: 5px solid #005fcc;
        outline-offset: 6px;
    }}

    #status {{
        margin-top: 24px;
        font-size: 30px;
        font-weight: 700;
    }}

    #words {{
        margin-top: 32px;
        padding: 28px;
        border: 4px solid #000;
        border-radius: 20px;
        min-height: 120px;
        background: #fff;
    }}

    #words .label {{
        font-size: 24px;
        margin-bottom: 14px;
        font-weight: 700;
    }}

    #words .text {{
        font-size: 42px;
        line-height: 1.5;
        white-space: pre-wrap;
    }}
    </style>
  </head>
  <body>
    <h2>LINEAR16 WebSocket Stream</h2>

    <!-- Start removed: button1/button2 will auto-start everything -->
    <button id="stop">Stop</button>
    <br/>
    <button id="b1">button1</button>
    <button id="b2">button2</button>

    <div id="status">Idle</div>

    <!-- words output -->
    <div id="words">
      <div class="label">Words</div>
      <div class="text" id="wordsText">—</div>
    </div>

    <script>
      // player:
      // - WebSocket: JSON header (text), then PCM int16 chunks (binary)
      // - WebAudio scheduling using nextTime

      // - We do this because without nextTime the packets would arrive at random times and the 
      // packets arrive randomly. 

      let ws = null;
      let ctx = null;
      let info = null; 
      let nextTime = 0;

      const statusEl = document.getElementById("status");
      //  words display element
      const wordsTextEl = document.getElementById("wordsText");

      //  global gain node for instant mute on Stop
      let global_gain = null;

      function ensureCtx() {{
        if (!ctx) {{
          ctx = new (window.AudioContext || window.webkitAudioContext)();

          //  create global gain once and route to destination
          global_gain = ctx.createGain();
          global_gain.gain.value = 1.0;
          global_gain.connect(ctx.destination);
        }}
        return ctx;
      }}

      function playChunk(u8) {{
        const c = ensureCtx();

        // bytes -> int16 -> float32

        //google tts gives us bytes as linear 16 bit, we interpret every 2 as int16
        // web audio accepts f32 so we convert to that as well. 

        const i16 = new Int16Array(u8.buffer, u8.byteOffset, u8.byteLength / 2);
        const f32 = new Float32Array(i16.length);
        for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;

        //normalize each signed integer into a floating point from [-1, 1] by dividing by the max integer

        const frames = f32.length / info.channels;
        const buf = c.createBuffer(info.channels, frames, info.sample_rate);
        buf.copyToChannel(f32, 0);

        // sound node handling:
        const src = c.createBufferSource(); 
        src.buffer = buf;
        // route audio through global_gain so Stop can mute immediately
        src.connect(global_gain);

        // schedule back-to-back, but keep a tiny safety lead
        const minStart = c.currentTime + {MIN_TIME};
        //handle case where lag happened and scheduled sound node is in the past or soon
        if (nextTime < minStart) nextTime = minStart;  

        src.start(nextTime);
        nextTime += buf.duration; 
        // We add the duration of this chunk onto the nextTime so that subsequent chunks
        // - will be queued after this chunk plays.
      }}

      //this establishes link between the browser and this FastAPI server
      function connect() {{
        const proto = location.protocol === "https:" ? "wss" : "ws";
        ws = new WebSocket(`${{proto}}://${{location.host}}/ws`);
        ws.binaryType = "arraybuffer";

        ws.onopen = () => statusEl.textContent = "Connected";

        ws.onmessage = (ev) => {{
          if (typeof ev.data === "string") {{
            const msg = JSON.parse(ev.data);
            if (msg.type === "header") {{
              info = {{ sample_rate: msg.sample_rate, channels: msg.channels }};
              statusEl.textContent = "Streaming...";
            }}
            //  show words on page
            if (msg.type === "words") {{
              const words = msg.words || [];
              wordsTextEl.textContent = words.length ? words.join(" ") : "—";
            }}
            return;
          }}
          if (!info) return;
          playChunk(new Uint8Array(ev.data));
        }};

        ws.onclose = () => {{ statusEl.textContent = "Disconnected"; ws = null; info = null; }};
        ws.onerror = () => statusEl.textContent = "WebSocket error";
      }}

      function stop() {{
        //  instant mute (kills already-scheduled audio immediately)
        if (global_gain) global_gain.gain.value = 0.0;

        if (!ws) return;
        try {{ ws.send(JSON.stringify({{type:"stop"}})); }} catch {{}} 
        ws.close();
        ws = null;
        info = null;
        statusEl.textContent = "Stopped";
      }}

      // ensure AudioContext is resumed AND WS is connected before sending button commands
      async function ensureConnected() {{
        const c = ensureCtx();
        if (c.state === "suspended") await c.resume();

        // If already open, done
        if (ws && ws.readyState === 1) return;

        // If no socket (or closed), create one
        if (!ws || ws.readyState === 3) {{
          connect();
        }}

        // Wait for CONNECTING -> OPEN
        if (ws && ws.readyState === 0) {{
          await new Promise((resolve, reject) => {{
            const timeoutMs = 2000;
            const start = performance.now();
            const timer = setInterval(() => {{
              if (ws && ws.readyState === 1) {{
                clearInterval(timer);
                resolve();
                return;
              }}
              if (performance.now() - start > timeoutMs) {{
                clearInterval(timer);
                reject(new Error("WebSocket open timeout"));
              }}
            }}, 20);
          }});
        }}
      }}

      document.getElementById("stop").onclick = stop;

      document.getElementById("b1").onclick = async () => {{
        nextTime = 0;
        await ensureConnected();
        //  unmute output for new playback
        if (global_gain) global_gain.gain.value = 1.0;
        ws.send(JSON.stringify({{type: "button1"}}));
      }};

      document.getElementById("b2").onclick = async () => {{
        nextTime = 0;
        await ensureConnected();
        //  unmute output for new playback
        if (global_gain) global_gain.gain.value = 1.0;
        ws.send(JSON.stringify({{type: "button2"}}));
      }};
    </script>
  </body>
</html>
"""





@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML_MIN


# -----------------------------
# WebSocket stream endpoint
# -----------------------------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    stop_event = asyncio.Event()
    stream_task: asyncio.Task | None = None

    async def stream_from_result(result: Tuple[np.ndarray, List[str]]):
        audio_np, words = result
        pcm = ndarray_to_linear16_bytes(audio_np)

        # Send header first (format info)
        await ws.send_json({
            "type": "header",
            "format": "LINEAR16",
            "sample_rate": AUDIO.sample_rate_hz,
            "channels": AUDIO.channels,
            "chunk_ms": AUDIO.chunk_ms,
        })

        # Send the recognized words (browser will render them)
        await ws.send_json({
            "type": "words",
            "words": words,
        })

        # Stream PCM bytes in fixed chunks
        for off in range(0, len(pcm), AUDIO.chunk_bytes):
            if stop_event.is_set():
                break
            await ws.send_bytes(pcm[off:off + AUDIO.chunk_bytes])

    try:
        while True:
            msg = await ws.receive_json() #button pres
            t = msg.get("type")

            stop_event.clear()
            if stream_task and not stream_task.done():
                stream_task.cancel()

            if t == "button1":
                stream_task = asyncio.create_task(stream_from_result(OCR()))

            elif t == "button2":
                stream_task = asyncio.create_task(stream_from_result(repeat()))

            elif t == "stop":
                stop_event.set()
                await ws.close()
                return

    except WebSocketDisconnect:
        stop_event.set()
        if stream_task and not stream_task.done():
            stream_task.cancel()
