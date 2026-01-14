import os
import json
import asyncio
import logging
import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

# Import the agent logic and config
from agent_config import RoyAgent, SESSION_CONFIG, SYSTEM_MESSAGE, INITIAL_GREETING_HINT

# ------------------------------------------------------------------------------
# SETUP & CONFIG
# ------------------------------------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
PUBLIC_WS_BASE = os.getenv("PUBLIC_WS_BASE")

# OpenAI Realtime API URL
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)
app = FastAPI()

# ------------------------------------------------------------------------------
# STARTUP EVENT (Visual Terminal Effect)
# ------------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Runs the visual agent introduction in the terminal when the server starts."""
    try:
        agent_visual = RoyAgent()
        await agent_visual.run_introduction()
    except Exception as e:
        logger.error(f"Error during visual startup: {e}")

# ------------------------------------------------------------------------------
# 0. TOOLS IMPLEMENTATION
# ------------------------------------------------------------------------------

async def check_order_status(order_id: str):
    logger.info(f"Executing tool: check_order_status for {order_id}")
    # Example logic
    if "123" in order_id:
        return json.dumps({"status": "shipped", "delivery_date": "2025-12-25"})
    else:
        return json.dumps({"status": "processing", "delivery_date": "unknown"})

AVAILABLE_TOOLS = {
    "check_order_status": check_order_status
}

# ------------------------------------------------------------------------------
# HELPER: Telnyx Actions
# ------------------------------------------------------------------------------

async def execute_telnyx_action(call_id: str, action: str, payload: dict = None):
    url = f"https://api.telnyx.com/v2/calls/{call_id}/actions/{action}"
    headers = {
        "Authorization": f"Bearer {TELNYX_API_KEY}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload or {})
            return response
        except Exception as e:
            logger.error(f"Failed to execute Telnyx action {action}: {e}")

# ------------------------------------------------------------------------------
# 1. TELNYX WEBHOOK
# ------------------------------------------------------------------------------

@app.post("/inbound")
async def inbound(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid_json"}

    data = body.get("data", {})
    event_type = data.get("event_type")
    payload = data.get("payload", {})
    call_id = payload.get("call_control_id", "UNKNOWN_ID")

    if event_type == "call.initiated":
        logger.info(f"Answering call: {call_id}")
        await execute_telnyx_action(call_id, "answer")
        return {"status": "answering"}

    if event_type == "call.answered":
        stream_url = f"{PUBLIC_WS_BASE}/media/{call_id}"
        logger.info(f"Starting Stream to: {stream_url}")
        
        # Using PCMA (A-Law) for best compatibility and low latency
        stream_payload = {
            "stream_url": stream_url,
            "stream_track": "inbound_track",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "PCMA" 
        }
        await execute_telnyx_action(call_id, "streaming_start", stream_payload)
        return {"status": "streaming_started"}

    return {"status": "ok"}

# ------------------------------------------------------------------------------
# 2. MAIN WEBSOCKET HANDLER
# ------------------------------------------------------------------------------

@app.websocket("/media/{call_id}")
async def media_handler(ws: WebSocket, call_id: str):
    await ws.accept()
    logger.info(f"Telnyx WebSocket accepted for Call ID: {call_id}")

    openai_ws = None
    forward_task = None
    stream_id = None

    try:
        # -----------------------------------------------------
        # PHASE 1: Wait for Telnyx 'start' event
        # -----------------------------------------------------
        start_received = False
        while not start_received:
            try:
                data = await ws.receive_json()
            except Exception:
                continue

            event = data.get("event")

            if event == "start":
                stream_id = data.get("start", {}).get("stream_id")
                if not stream_id:
                    stream_id = data.get("stream_id")
                
                logger.info(f"Media stream started. Stream ID: {stream_id}")
                start_received = True
            
            elif event in ("stop", "callEnded"):
                logger.info("Call ended before stream started.")
                return

        # -----------------------------------------------------
        # PHASE 2: Connect to OpenAI Realtime
        # -----------------------------------------------------
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        openai_ws = await websockets.connect(OPENAI_REALTIME_URL, additional_headers=headers)
        logger.info("Connected to OpenAI Realtime API")

        # -----------------------------------------------------
        # PHASE 3: Define Inner Function (OpenAI -> Telnyx)
        # -----------------------------------------------------
        async def handle_openai_events():
            try:
                async for message in openai_ws:
                    event = json.loads(message)
                    event_type = event.get("type")

                    if event_type == "error":
                        logger.error(f"OpenAI Error: {event}")

                    # 1. AUDIO HANDLING
                    elif event_type == "response.audio.delta":
                        audio_payload = event.get("delta")
                        if audio_payload and stream_id:
                            await ws.send_json({
                                "event": "media",
                                "stream_id": stream_id,
                                "media": {"payload": audio_payload}
                            })
                    
                    # 2. INTERRUPTION HANDLING (BARGE-IN)
                    elif event_type == "input_audio_buffer.speech_started":
                        logger.info("User started speaking (Interruption detected) -> Clearing Buffer")
                        
                        # Command Telnyx to clear the buffer immediately
                        if stream_id:
                            await ws.send_json({
                                "event": "clear",
                                "stream_id": stream_id
                            })
                        
                        # Cancel OpenAI response generation
                        await openai_ws.send(json.dumps({"type": "response.cancel"}))

                    # 3. LOGGING
                    elif event_type == "response.created":
                        logger.info("AI started generating response...")
                    elif event_type == "response.audio_transcript.done":
                        logger.info(f"AI: {event.get('transcript')}")
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        logger.info(f"USER: {event.get('transcript', '').strip()}")

                    # 4. TOOL CALLING
                    elif event_type == "response.function_call_arguments.done":
                        f_call_id = event.get("call_id")
                        f_name = event.get("name")
                        f_args = json.loads(event.get("arguments"))
                        
                        logger.info(f"Tool Call: {f_name} | Args: {f_args}")
                        
                        if f_name in AVAILABLE_TOOLS:
                            result = await AVAILABLE_TOOLS[f_name](**f_args)
                            
                            # Send tool output back to OpenAI
                            await openai_ws.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": f_call_id,
                                    "output": result
                                }
                            }))
                            # Request a new response based on the tool output
                            await openai_ws.send(json.dumps({"type": "response.create"}))

            except Exception as e:
                logger.error(f"Error in handle_openai_events: {e}")

        # -----------------------------------------------------
        # PHASE 4: Start Listening
        # -----------------------------------------------------
        forward_task = asyncio.create_task(handle_openai_events())
        await asyncio.sleep(0.2)

        # -----------------------------------------------------
        # PHASE 5: Send Configuration (Injecting the Agent Brain)
        # -----------------------------------------------------
        logger.info("Sending session update from agent_intro...")
        
        session_update = {
            "type": "session.update",
            "session": {
                **SESSION_CONFIG,       # Unpacking config from agent_intro.py
                "modalities": ["text", "audio"],
                "instructions": SYSTEM_MESSAGE
            }
        }
        await openai_ws.send(json.dumps(session_update))

        logger.info("Sending initial greeting...")
        await openai_ws.send(json.dumps({
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": INITIAL_GREETING_HINT
            }
        }))

        # -----------------------------------------------------
        # PHASE 6: Main Loop (Telnyx -> OpenAI)
        # -----------------------------------------------------
        async for message in ws.iter_text():
            try:
                data = json.loads(message)
                event = data.get("event")

                if event == "media":
                    media_payload = data["media"]["payload"]
                    await openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": media_payload
                    }))
                
                elif event == "stop":
                    logger.info("Telnyx sent STOP event.")
                    break
            except Exception as e:
                logger.error(f"Error parsing Telnyx message: {e}")
                break

    except WebSocketDisconnect:
        logger.info("Telnyx WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Unexpected error in media_handler: {e}")
    finally:
        if forward_task:
            forward_task.cancel()
        if openai_ws:
            await openai_ws.close()
        logger.info(f"Session closed for {call_id}")
