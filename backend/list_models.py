from google import genai
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Models that support embedContent:\n")
for m in client.models.list():
    for action in m.supported_actions:
        if action == "embedContent":
            print(m.name)