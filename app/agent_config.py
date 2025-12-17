import os
from dotenv import load_dotenv
load_dotenv()
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN")