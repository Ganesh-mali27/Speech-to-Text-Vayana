import os
import argparse
import sys
import logging
from pathlib import Path

# Set up package paths so we can run directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import AUDIO_DIR, is_api_configured, SARVAM_API_KEY, OUTPUT_DIR, OUTPUT_FLAGGED_DIR
from src.pipeline_S2T_1 import TranscriptionPipeline
from src.pipeline_flagged_2 import FlaggedPipeline
from src.pipeline_intent_3 import IntentPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="Sarvam AI Speech-to-Text CLI Pipeline with Diarization and Transliteration"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file", "-f",
        type=str,
        help="Path to a single audio file to process."
    )
    group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Process all audio files inside the Audios/ folder."
    )

    parser.add_argument(
        "--lang", "-l",
        type=str,
        default="unknown",
        help="Source language code (e.g. hi-IN, ta-IN). Default is 'unknown' for automatic detection."
    )
    parser.add_argument(
        "--speakers", "-s",
        type=int,
        default=None,
        help="Expected number of speakers (1-10). If omitted, the model auto-detects speaker count."
    )
    parser.add_argument(
        "--poll-interval", "-p",
        type=int,
        default=15,
        help="Polling interval in seconds for batch jobs (default: 15)."
    )

    args = parser.parse_args()

    # 1. Check API Key
    if not is_api_configured():
        logger.error("Sarvam API Key is not configured!")
        logger.error("Please edit the .env file in the project root and add your SARVAM_API_KEY.")
        sys.exit(1)

    # 2. Collect files
    file_paths = []
    if args.all:
        logger.info(f"Scanning directory: {AUDIO_DIR}")
        if not AUDIO_DIR.exists():
            logger.error(f"Audios folder does not exist at: {AUDIO_DIR}")
            sys.exit(1)
        
        # Supported audio formats
        extensions = [".wav", ".mp3", ".aac", ".flac", ".ogg"]
        for path in AUDIO_DIR.iterdir():
            if path.is_file() and path.suffix.lower() in extensions:
                file_paths.append(str(path))
        
        if not file_paths:
            logger.error("No valid audio files found in the Audios/ folder.")
            sys.exit(1)
    else:
        file_paths = [args.file]

    logger.info(f"Processing {len(file_paths)} audio file(s): {[os.path.basename(f) for f in file_paths]}")

    # 3. Execute pipeline_S2T_1
    try:
        pipeline = TranscriptionPipeline()
        results = pipeline.run_on_files(
            file_paths=file_paths,
            language_code=args.lang,
            num_speakers=args.speakers,
            poll_interval_sec=args.poll_interval
        )
        
        logger.info("=" * 60)
        logger.info("Pipeline executed successfully!")
        logger.info(f"Processed {len(results)} file(s).")
        logger.info("Transcripts and JSON files have been saved to the 'outputs/' directory.")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        sys.exit(1)


    # 4. Execute Pipeline_FLAGGED LLM Gemini
    logger.info("Starting Flagged Keywords Extraction using Gemini...")
    try:
        flagged_pipeline = FlaggedPipeline()
        for file_path in file_paths:
            base_name = Path(file_path).stem
            processed_json_path = OUTPUT_DIR / f"{base_name}_processed.json"
            if processed_json_path.exists():
                output_path = flagged_pipeline.process_file(processed_json_path)
                if output_path:
                    logger.info(f"Generated flagged keywords JSON: {output_path.name}")
            else:
                logger.warning(f"Processed JSON not found for {base_name}: {processed_json_path}")
        logger.info("Flagged keywords extraction finished.")
    except Exception as e:
        logger.error(f"Flagged keywords extraction failed: {e}", exc_info=True)


    # 5. Execute the Intent Detection
    logger.info("Starting Intent Detection using Gemini...")
    try:
        intent_pipeline = IntentPipeline()
        for file_path in file_paths:
            base_name = Path(file_path).stem
            flagged_json_filename = f"flagged_{base_name}_processed.json"
            flagged_json_path = OUTPUT_FLAGGED_DIR / flagged_json_filename
            if flagged_json_path.exists():
                output_path = intent_pipeline.process_file(flagged_json_path)
                if output_path:
                    logger.info(f"Generated intent detection JSON: {output_path.name}")
            else:
                logger.warning(f"Flagged JSON not found for {base_name}: {flagged_json_path}")
        logger.info("Intent detection finished.")
    except Exception as e:
        logger.error(f"Intent detection failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
