import os
import argparse
import sys
import logging
from pathlib import Path

# Add parent directory to sys.path to resolve imports correctly
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import AUDIO_DIR, is_api_configured
from src.pipeline_S2T_1 import TranscriptionPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="Sarvam AI Speech-to-Text Pipeline with Diarization and Transliteration"
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

    # 3. Execute pipeline
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

if __name__ == "__main__":
    main()
