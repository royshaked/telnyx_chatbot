# Telnyx Realtime AI Voice Agent

This project implements a **Real-time Voice Agent** integrating **Telnyx** telephony services with **OpenAI's Realtime API** (GPT-4o).

The system acts as an intelligent voice bot capable of answering calls, maintaining a natural low-latency conversation, handling interruptions (barge-in), and executing logical actions (Function Calling).

Currently, the bot is configured as an introductory agent for **Roy Shaked**, but the infrastructure is designed to be easily adapted for any other use case.

## 🚀 Key Features

* **Real-time Conversation:** Utilizes WebSockets for bidirectional audio streaming between Telnyx and OpenAI.
* **Audio Quality:** Supports **G.711 PCMA (A-Law)** codec for high compatibility and minimal latency.
* **Interruption Handling (Barge-in):** The system detects when the user starts speaking while the bot is talking, immediately stops audio playback, and clears the buffer to listen to the user.
* **Tool Calling:** Demonstrates the ability to execute code functions (e.g., `check_order_status`) and return the result to the conversation flow.
* **Visual Terminal Effect:** Displays a "retro terminal" visual effect in the console upon server startup, simulating the agent's initialization.

## 🛠️ Tech Stack

* **Python 3.10+**
* **[FastAPI](https://fastapi.tiangolo.com/):** For managing the Webhook and WebSockets.
* **[OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime):** The intelligence behind the conversation (`gpt-4o-mini-realtime-preview`).
* **[Telnyx API](https://telnyx.com/):** Handles call control and media streaming.

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/royshaked/telnyx_chatbot.git](https://github.com/royshaked/telnyx_chatbot.git)
    cd telnyx_chatbot
    ```

2.  **Create a virtual environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

Create a `.env` file in the root directory and add the following variables:

```env
OPENAI_API_KEY=sk-proj-...       # Your OpenAI API Key
TELNYX_API_KEY=KEY017...         # Your Telnyx API Key
PUBLIC_WS_BASE=wss://your-url.com # Your server's public WebSocket URL