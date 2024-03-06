import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]
GUILD = os.environ["GUILD_ID"]
HF_TOKEN = os.environ.get("HF_TOKEN")
GEMINI_TOKEN = os.environ.get("GEMINI_TOKEN")
DB_CONN = os.environ.get("DB_CONN")
ERROR_WH = os.environ.get("ERROR_WH")

COGS_DIR = "cogs"
