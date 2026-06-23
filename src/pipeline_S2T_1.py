import os
import time
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import SARVAM_API_KEY, SARVAM_BASE_URL, OUTPUT_DIR, AUDIO_DIR, is_api_configured
from src.sarvam_client import SarvamClient

logger = logging.getLogger(__name__)

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

class TranscriptionPipeline:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SARVAM_API_KEY
        if not self.api_key:
            raise ValueError(
                "Sarvam API key is not configured. Please set SARVAM_API_KEY in your .env file."
            )
        self.client = SarvamClient(api_key=self.api_key, base_url=SARVAM_BASE_URL)

    def run_on_files(
        self,
        file_paths: List[str],
        language_code: str = "unknown",
        num_speakers: Optional[int] = None,
        poll_interval_sec: int = 15,
        max_poll_attempts: int = 240 # 1 hour max by default
    ) -> List[Dict[str, Any]]:
        """
        Runs the end-to-end transcription and transliteration pipeline on a list of audio files.
        """
        if not file_paths:
            logger.warning("No audio files provided to process.")
            return []

        # Validate that all files exist
        valid_paths = []
        for path in file_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                valid_paths.append(abs_path)
            else:
                logger.error(f"File does not exist: {path}")

        if not valid_paths:
            raise FileNotFoundError("None of the provided audio files exist.")

        filenames = [os.path.basename(path) for path in valid_paths]
        
        # 1. Initiate job
        job_info = self.client.create_job(
            language_code=language_code,
            with_diarization=True,
            num_speakers=num_speakers
        )
        job_id = job_info.get("job_id")
        if not job_id:
            raise RuntimeError("Initiating batch job failed: Did not receive job_id.")

        # 2. Get upload URLs
        upload_urls = self.client.get_upload_urls(job_id, filenames)
        
        # 3. Upload files
        for file_path in valid_paths:
            fname = os.path.basename(file_path)
            if fname not in upload_urls:
                raise RuntimeError(f"Could not get upload URL for file {fname}")
            self.client.upload_file(upload_urls[fname], file_path)

        # 4. Start job
        self.client.start_job(job_id)
        logger.info(f"Job {job_id} started successfully. Monitoring status...")

        # 5. Poll status
        job_completed = False
        status_data = {}
        for attempt in range(max_poll_attempts):
            time.sleep(poll_interval_sec)
            status_data = self.client.get_job_status(job_id)
            state = status_data.get("job_state")
            logger.info(f"Polling Attempt {attempt + 1}: Job State is '{state}'")

            if state in ["Completed", "PartiallyCompleted"]:
                job_completed = True
                break
            elif state in ["Failed", "Cancelled"]:
                raise RuntimeError(f"Job processing failed on Sarvam side with state: {state}")

        if not job_completed:
            raise TimeoutError(f"Job execution timed out. Current state: {status_data.get('job_state')}")

        logger.info("Transcription job finished. Retrieving results...")

        # 6. Map job details and download output files
        job_details = status_data.get("job_details", [])
        output_files_to_download = []
        audio_to_output_mapping = {}

        for detail in job_details:
            inputs = detail.get("inputs", [])
            outputs = detail.get("outputs", [])
            state = detail.get("state", detail.get("status"))

            if state == "Failed" or detail.get("error_message"):
                logger.error(f"Processing failed for a file: {detail.get('error_message')}")
                continue

            # Extract the original filename from the inputs list
            orig_name = None
            if inputs:
                orig_name = inputs[0].get("file_name")
            if not orig_name:
                orig_name = detail.get("file_name")

            for out in outputs:
                out_name = out.get("file_name")
                if out_name:
                    output_files_to_download.append(out_name)
                    if orig_name:
                        audio_to_output_mapping[orig_name] = out_name

        if not output_files_to_download:
            raise RuntimeError("No transcription output files available to download.")

        downloaded_json_contents = self.client.download_results(job_id, output_files_to_download)

        # 7. Post-process: Transliteration & Output Generation
        processed_results = []
        for file_path in valid_paths:
            fname = os.path.basename(file_path)
            output_json_name = audio_to_output_mapping.get(fname)
            
            if not output_json_name or output_json_name not in downloaded_json_contents:
                logger.error(f"No downloaded transcription found for audio file {fname}")
                continue

            raw_result = downloaded_json_contents[output_json_name]
            
            # Post process this result
            processed_data = self.post_process_result(fname, raw_result)
            processed_results.append(processed_data)

        return processed_results

    def post_process_result(self, audio_filename: str, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract transcripts, run transliteration on non-English text, and generate output files.
        """
        logger.info(f"Post-processing result for {audio_filename}...")
        
        # Extract metadata
        meta = raw_result.get("metadata", {})
        detected_lang = raw_result.get("language_code", meta.get("language", "hi-IN"))
        model = meta.get("model", "saaras:v3")
        
        # Try diarized_transcript entries first, fallback to segments
        segments = raw_result.get("diarized_transcript", {}).get("entries", [])
        if not segments:
            segments = raw_result.get("segments", [])
            
        transcript = raw_result.get("transcript", "")
        
        # Check if translation or transliteration is needed (required for non-English languages)
        # We assume English is 'en-IN' or 'en'.
        is_english = detected_lang.lower().startswith("en")
        
        processed_segments = []
        full_transliteration = []

        logger.info(f"Detected language: {detected_lang}. Needs transliteration: {not is_english}")

        for i, segment in enumerate(segments):
            try:
                start = float(segment.get("start_time_seconds", segment.get("start_time", 0.0)))
            except (ValueError, TypeError):
                start = 0.0
                
            try:
                end = float(segment.get("end_time_seconds", segment.get("end_time", 0.0)))
            except (ValueError, TypeError):
                end = 0.0
                
            text = segment.get("transcript", segment.get("text", "")).strip()
            
            spk_id = segment.get("speaker_id")
            if spk_id is not None:
                speaker = f"SPEAKER {spk_id}"
            else:
                speaker = segment.get("speaker", "SPEAKER 00")
                
            speaker = speaker.upper().replace("SPEAKER_", "SPEAKER ")
            
            processed_seg = {
                "start_time": start,
                "end_time": end,
                "speaker": speaker,
                "text": text,
                "transliterated_text": ""
            }

            if text and not is_english:
                # Transliterate the segment native script to Roman (Latin) script
                translit_text = self.client.transliterate(
                    text=text,
                    source_language_code=detected_lang,
                    target_language_code="en-IN"
                )
                processed_seg["transliterated_text"] = translit_text
                full_transliteration.append(f"({speaker}): {translit_text}")
            else:
                processed_seg["transliterated_text"] = text

            processed_segments.append(processed_seg)

        # Build output path prefixes
        base_name = Path(audio_filename).stem
        
        # Compile processed data structure
        output_data = {
            "audio_filename": audio_filename,
            "detected_language": detected_lang,
            "model_used": model,
            "original_transcript": transcript,
            "segments": processed_segments
        }

        # 1. Save detailed JSON
        json_path = OUTPUT_DIR / f"{base_name}_processed.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved processed JSON to {json_path}")

        # 2. Save readable text transcript
        txt_path = OUTPUT_DIR / f"{base_name}_transcript.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"--- TRANSCRIPT FOR {audio_filename} ---\n")
            f.write(f"Detected Language: {detected_lang}\n")
            f.write(f"Model: {model}\n\n")
            
            for seg in processed_segments:
                start_str = format_timestamp(seg["start_time"])
                end_str = format_timestamp(seg["end_time"])
                spk = seg["speaker"]
                
                f.write(f"[{start_str} - {end_str}] {spk}:\n")
                if not is_english:
                    f.write(f"  Native Script:   {seg['text']}\n")
                    f.write(f"  Transliterated:  {seg['transliterated_text']}\n")
                else:
                    f.write(f"  Text:            {seg['text']}\n")
                f.write("\n")
        logger.info(f"Saved readable text transcript to {txt_path}")

        # 3. Save CSV version
        csv_path = OUTPUT_DIR / f"{base_name}_transcript.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Start Time", "End Time", "Speaker", "Original Text", "Transliterated Text"])
            for seg in processed_segments:
                writer.writerow([
                    seg["start_time"],
                    seg["end_time"],
                    seg["speaker"],
                    seg["text"],
                    seg["transliterated_text"]
                ])
        logger.info(f"Saved CSV transcript to {csv_path}")

        return output_data
