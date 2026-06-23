import sys
import requests
from pathlib import Path

# Add parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import is_api_configured, SARVAM_API_KEY
from src.sarvam_client import SarvamClient

def main():
    print("Checking Sarvam AI STT Pipeline setup...")
    print(f"API Key configured: {is_api_configured()}")
    
    if not is_api_configured():
        print("[Error] API Key is not set in your .env file or environment.")
        print("Please add 'SARVAM_API_KEY=your_key' to .env in the project root.")
        return

    print("Attempting connection to Sarvam AI API...")
    client = SarvamClient(api_key=SARVAM_API_KEY)
    
    # Try a quick transliteration request to test API key validity
    try:
        test_text = "नमस्ते दुनिया"
        print(f"Testing Transliterate API with: '{test_text}'")
        result = client.transliterate(
            text=test_text,
            source_language_code="hi-IN",
            target_language_code="en-IN"
        )
        print("[OK] Connection successful!")
        print(f"Transliterated output: '{result}'")
    except Exception as e:
        print(f"[Error] Connection/API test failed: {e}")
        print("Please check if your API key is active and has correct subscription permissions.")

if __name__ == "__main__":
    main()
