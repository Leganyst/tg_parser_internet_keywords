import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
FUZZY_THRESHOLD = int(os.getenv("FUZZY_THRESHOLD", "80"))
KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", "keywords.txt")