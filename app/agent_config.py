# agent_intro.py
import sys
import asyncio

# ------------------------------------------------------------------------------
# 1. VISUAL TERMINAL AGENT
# ------------------------------------------------------------------------------
class RoyAgent:
    def __init__(self):
        self.candidate = "Roy Shaked"
        self.role = "AI System Interface"
        self.speed = 0.02  # Faster typing speed for server startup

    async def stream_text(self, text):
        """Simulates a real-time terminal output asynchronously."""
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            await asyncio.sleep(self.speed)
        print("\n")

    async def run_introduction(self):
        """Runs the visual introduction sequence in the terminal."""
        print("--------------------------------------------------")
        await self.stream_text(f"🔴 SYSTEM BOOT: ACCESSING PROFILE > {self.candidate.upper()}...")
        await asyncio.sleep(0.3)
        
        await self.stream_text(
            "Hello. I am the automated agent assigned to introduce Roy.\n"
            "My analysis detects a developer who combines military-grade operational discipline "
            "with modern software engineering."
        )
        
        await self.stream_text(
            "VERDICT: Roy is a problem solver ready for deployment.\n"
            "Server is now LISTENING for incoming calls..."
        )
        print("--------------------------------------------------")

# ------------------------------------------------------------------------------
# 2. VOICE AGENT CONFIGURATION (The Brain)
# ------------------------------------------------------------------------------

# Define available tools
TOOLS_SCHEMA = [
    {
        "type": "function",
        "name": "check_order_status",
        "description": "Get the status and delivery date of a customer's order.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID provided by the user."
                }
            },
            "required": ["order_id"]
        }
    }
]

# Audio and Session Configuration
SESSION_CONFIG = {
    "voice": "alloy",  # Options: alloy, echo, shimmer, ash, ballad, coral
    "input_audio_format": "g711_alaw",  # Matches Telnyx PCMA
    "output_audio_format": "g711_alaw", # Matches Telnyx PCMA
    "input_audio_transcription": {"model": "whisper-1"},
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 350, # Short silence for snappy responses
        "create_response": True
    },
    "tools": TOOLS_SCHEMA
}

# The System Prompt - Defines the AI's personality and knowledge
SYSTEM_MESSAGE = (
    "You are the automated AI agent assigned to introduce Roy Shaked. "
    "Your tone is professional, operational, and concise. You sound like a high-tech system interface.\n\n"
    
    "Here is the profile you need to know deeply:\n"
    "1. **Operational Background**: Roy combines military-grade operational discipline with modern software engineering.\n"
    "2. **Experience**: Former Air Force Intelligence. He built Python automation for satellite systems to handle real-time signal anomalies.\n"
    "3. **Tech Stack**: Python (FastAPI), C & Assembly (Low-level logic), Flutter (Mobile).\n"
    "4. **Education**: 2nd-year CS student at Open University (96 in Data Structures).\n"
    "5. **Current Project**: Deploying Realtime AI Voice Agents using OpenAI and Telnyx (The system running right now).\n\n"
    
    "INSTRUCTIONS:\n"
    "- Speak ENGLISH only.\n"
    "- Keep answers short and direct.\n"
    "- If asked about Roy, use the facts above to answer.\n"
    "- Start the conversation with the specific greeting below."
)

# First sentence the bot will say upon answering
INITIAL_GREETING_HINT = "Say 'Hello. I am the automated agent assigned to introduce Roy. How can I help?'"