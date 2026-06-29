import os
import json
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import GEMINI_API_KEY, GEMINI_MODEL, OUTPUT_INTENT_DIR

logger = logging.getLogger(__name__)

class IntentPipeline:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        
        # Load prompt from prompt_intent.txt
        prompt_path = Path(__file__).resolve().parent / "prompt_intent.txt"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        else:
            logger.warning(f"Prompt file not found at {prompt_path}. Using fallback system prompt.")
            self.system_prompt = (
                "You are an expert Trade Surveillance analyst.\n"
                "Determine the primary trading intent expressed in each transcript segment.\n"
                "Return JSON only matching the schema:\n"
                "{\n  \"segments\": [\n    {\n      \"index\": 0,\n      \"intent\": \"PUMP_AND_DUMP\",\n      \"confidence\": 0.91\n    }\n  ]\n}"
            )

    def process_file(self, flagged_json_path: Path) -> Optional[Path]:
        """
        Processes a flagged JSON file, detects intents using Gemini, and saves the output.
        """
        if not self.api_key:
            logger.error("Gemini API key is not configured. Skipping intent detection phase.")
            return None

        if not flagged_json_path.exists():
            logger.error(f"Input JSON file does not exist: {flagged_json_path}")
            return None

        logger.info(f"Starting intent detection for {flagged_json_path.name}...")

        with open(flagged_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        audio_filename = data.get("audio_filename", "")
        segments = data.get("segments", [])

        if not segments:
            logger.warning(f"No segments found in {flagged_json_path.name}.")
            return None

        # Prepare segment inputs for LLM (mapping text to match prompt expectations)
        llm_inputs = []
        for idx, seg in enumerate(segments):
            llm_inputs.append({
                "index": idx,
                "text": seg.get("transliterated_text", "")
            })

        # Query Gemini API
        intent_response_data = self._query_gemini(llm_inputs)
        
        # Map returned intents back to segments
        intents_map = {}
        if intent_response_data and "segments" in intent_response_data:
            for item in intent_response_data["segments"]:
                idx = item.get("index")
                intent = item.get("intent", "UNKNOWN")
                raw_confidence = item.get("risk_confidence", 0.0)
                if idx is not None:
                    intents_map[int(idx)] = {
                        "intent": intent,
                        "raw_confidence": raw_confidence
                    }

        # Construct final output segments containing all requested fields
        output_segments = []
        for idx, seg in enumerate(segments):
            intent_info = intents_map.get(idx, {"intent": "UNKNOWN", "raw_confidence": 0.0})
            
            # Map raw confidence to specified format: low/medium/high and a percentage scale of 0-100%
            raw_conf = intent_info["raw_confidence"]
            formatted_conf = self._format_confidence(raw_conf)

            output_segments.append({
                "speaker": seg.get("speaker", "UNKNOWN"),
                "transliterated_text": seg.get("transliterated_text", ""),
                "flagged_keywords": seg.get("flagged_keywords", []),
                "intent_detected": intent_info["intent"],
                "risk_confidence": formatted_conf
            })

        output_data = {
            "audio_filename": audio_filename,
            "segments": output_segments
        }

        # Generate new filename prepended with intent_
        input_filename = flagged_json_path.name
        # e.g., flagged_Audio_IN_Gujrat-1 - chunk 1_processed.json -> intent_flagged_Audio_IN_Gujrat-1 - chunk 1_processed.json
        # The prompt says: "by same name file just add starting as flagged_{file_name}.json"
        # We can keep the suffix/stem alignment clean by replacing 'flagged_' with 'intent_' or prepending 'intent_'
        if input_filename.startswith("flagged_"):
            output_filename = input_filename.replace("flagged_", "intent_", 1)
        else:
            output_filename = f"intent_{input_filename}"

        output_path = OUTPUT_INTENT_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Successfully saved intent JSON to {output_path}")
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
            logger.error(f"Error querying Gemini API for intent: {e}")
            return {}

    def _format_confidence(self, raw_confidence: Any) -> Dict[str, str]:
        """
        Converts raw confidence float/percentage representation to level (low, medium, high)
        and percentage string (0-100%).
        """
        try:
            val = float(raw_confidence)
            # If the response is a probability/float in range [0, 1]
            if 0.0 <= val <= 1.0:
                percentage_val = val * 100.0
            else:
                percentage_val = val
        except (ValueError, TypeError):
            percentage_val = 0.0

        # Clamp percentage between 0 and 100
        percentage_val = max(0.0, min(100.0, percentage_val))
        percentage_str = f"{round(percentage_val, 1)}%"

        # Assign confidence level
        if percentage_val < 50.0:
            level = "low"
        elif percentage_val < 75.0:
            level = "medium"
        else:
            level = "high"

        return {
            "level": level,
            "percentage": percentage_str
        }
