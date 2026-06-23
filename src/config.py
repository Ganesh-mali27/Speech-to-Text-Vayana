import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "Audios"
OUTPUT_DIR = BASE_DIR / "outputs_audios"
OUTPUT_FLAGGED_DIR = BASE_DIR / "outputs_flagged"

# Create directories if they do not exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FLAGGED_DIR.mkdir(parents=True, exist_ok=True)

# Sarvam AI configurations
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE_URL = "https://api.sarvam.ai"
SARVAM_DEFAULT_MODEL = "saaras:v3"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def is_api_configured() -> bool:
    """Check if the Sarvam API key is configured."""
    return bool(SARVAM_API_KEY and SARVAM_API_KEY != "your_sarvam_api_key_here")

