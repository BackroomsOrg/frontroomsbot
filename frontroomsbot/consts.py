import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("GUILD_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
GEMINI_TOKEN = os.getenv("GEMINI_TOKEN")
DB_CONN = os.getenv("DB_CONN")

COGS_DIR = "cogs"
