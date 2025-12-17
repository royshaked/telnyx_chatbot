import os
import json
import asyncio
import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .utils.telnyx_http import telnyx_cmd
from .agent_config import TELNYX_API_KEY, OPENAI_API_KEY, PUBLIC_DOMAIN

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Health
# -----------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# -----------------------------
# Telnyx webhook
# -----------------------------
@app.post("/webhook")
async def telnyx_webhook(request: Request):
    event = await request.json()
    data = event.get("data", {})
    payload = data.get("payload", {})
    ev_type = data.get("event_type")
    call_control_id = payload.get("call_control_id")

    if not call_control_id:
        return JSONResponse({"status": "ignored"})

    if ev_type == "call.initiated":
        await telnyx_cmd(call_control_id, "answer", TELNYX_API_KEY)

        stream_url = f"wss://{PUBLIC_DOMAIN}/telnyx_media"
        body = {
            "stream_url": stream_url,
            "stream_track": "inbound_track",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "PCMU"
        }
        await telnyx_cmd(call_control_id, "streaming_start", TELNYX_API_KEY, body)

    return JSONResponse({"status": "ok"})

# -----------------------------
# Telnyx Media WebSocket
# -----------------------------
@app.websocket("/telnyx_media")
async def telnyx_media(ws: WebSocket):
    await ws.accept()
    logger.info("Telnyx WS connected")

    import websockets

    openai_ws = None
    stream_id = None

    try:
        # Wait for start frame
        while True:
            msg = await ws.receive_json()
            if msg.get("event") == "start":
                stream_id = msg.get("stream_id")
                break

        # Connect to OpenAI Realtime (TRANSCRIPTION ONLY)
        uri = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

        openai_ws = await websockets.connect(uri, additional_headers=headers)

        # Configure session – NO AUDIO OUTPUT
        session_update = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": [],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "transcription": {
                            "model": "whisper-1"
                        },
                        "turn_detection": {
                            "type": "semantic_vad"
                        }
                    }
                }
            }
        }

        await openai_ws.send(json.dumps(session_update))

        async def read_openai_events():
            async for message in openai_ws:
                event = json.loads(message)
                etype = event.get("type")

                if etype == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    if transcript:
                        logger.info(f"[TRANSCRIPT] {transcript}")

                        # כאן תוכל:
                        # - לשמור ל-DB
                        # - לשלוח ל-API
                        # - לצרף ל-Kafka
                        # - לכתוב לקובץ

        task = asyncio.create_task(read_openai_events())

        # Telnyx → OpenAI (audio only)
        async for msg in ws.iter_json():
            if msg.get("event") == "media":
                payload = msg["media"]["payload"]
                await openai_ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": payload
                }))

            elif msg.get("event") in ("stop", "callEnded"):
                break

    except WebSocketDisconnect:
        logger.info("Telnyx disconnected")

    finally:
        if openai_ws:
            await openai_ws.close()
        await ws.close()
