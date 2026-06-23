import os
import json
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import GEMINI_API_KEY, GEMINI_MODEL, OUTPUT_DIR, OUTPUT_FLAGGED_DIR

logger = logging.getLogger(__name__)

class FlaggedPipeline:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        
        # Load prompt from file
        # prompt_path = Path(__file__).resolve().parent / "prompt_1.txt"
        prompt_path = Path(__file__).resolve().parent / "prompt.txt"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        else:
            self.system_prompt = (
                "You are an expert conversational analysis assistant.\n"
                "Your task is to analyze the transliterated text of segments from an audio conversation and flag important keywords or key phrases.\n"
                "Extract important keywords or key phrases that represent the core topics or key details discussed in each segment.\n"
                "Respond strictly in JSON format matching the schema:\n"
                "{\n  \"flagged_segments\": [\n    {\n      \"index\": 0,\n      \"flagged_keywords\": [\"keyword1\", \"keyword2\"]\n    }\n  ]\n}"
            )

    def process_file(self, processed_json_path: Path) -> Optional[Path]:
        """
        Processes a single processed JSON file, extracts keywords using Gemini, and saves the output.
        """
        if not self.api_key:
            logger.error("Gemini API key is not configured. Skipping flagging phase.")
            return None

        if not processed_json_path.exists():
            logger.error(f"Input JSON file does not exist: {processed_json_path}")
            return None

        logger.info(f"Starting keyword flagging for {processed_json_path.name}...")

        with open(processed_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        audio_filename = data.get("audio_filename", "")
        segments = data.get("segments", [])

        if not segments:
            logger.warning(f"No segments found in {processed_json_path.name}.")
            return None

        # Prepare segment inputs for LLM
        llm_inputs = []
        for idx, seg in enumerate(segments):
            llm_inputs.append({
                "index": idx,
                "text": seg.get("transliterated_text", "")
            })

        # Query Gemini API
        flagged_data = self._query_gemini(llm_inputs)
        
        # Map returned keywords back to segments
        keywords_map = {}
        if flagged_data and "flagged_segments" in flagged_data:
            for item in flagged_data["flagged_segments"]:
                idx = item.get("index")
                kws = item.get("flagged_keywords", [])
                if idx is not None:
                    keywords_map[int(idx)] = kws

        # Construct final output segments containing speaker, transliterated_text, and flagged_keywords
        output_segments = []
        for idx, seg in enumerate(segments):
            output_segments.append({
                "speaker": seg.get("speaker", "UNKNOWN"),
                "transliterated_text": seg.get("transliterated_text", ""),
                "flagged_keywords": keywords_map.get(idx, [])
            })

        output_data = {
            "audio_filename": audio_filename,
            "segments": output_segments
        }

        # Generate new filename
        input_filename = processed_json_path.name
        # e.g., Audio_IN_Gujrat-1 - chunk 1_processed.json
        # replace _processed.json or just prepend flagged_
        # "by same name file just add starting as flagged_{file_name}.json"
        # Wait, if user wants flagged_{file_name}.json, where file_name is the original/processed file name.
        # Let's check: "by same name file just add starting as flagged_{file_name}.json"
        # If the input file is Audio_IN_Gujrat-1 - chunk 1_processed.json,
        # then flagged_Audio_IN_Gujrat-1 - chunk 1_processed.json (or similar) or flagged_Audio_IN_Gujrat-1 - chunk 1.json?
        # Let's keep the name: flagged_{input_filename}
        output_filename = f"flagged_{input_filename}"
        output_path = OUTPUT_FLAGGED_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Successfully saved flagged JSON to {output_path}")
        return output_path

    def _query_gemini(self, llm_inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sends the segment texts to Gemini API and returns the parsed JSON response.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        prompt_content = f"{self.system_prompt}\n\nInput segments:\n{json.dumps(llm_inputs, ensure_ascii=False)}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_content}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            res_json = response.json()
            
            # Extract generated text
            candidates = res_json.get("candidates", [])
            if not candidates:
                logger.error("Gemini response is empty or has no candidates.")
                return {}
            
            text_response = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            return json.loads(text_response)
        except Exception as e:
            logger.error(f"Error querying Gemini API: {e}")
            return {}
