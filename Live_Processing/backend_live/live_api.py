import os
import uuid
import json
import asyncio
import subprocess
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import sys

# Setup paths to import from src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.pipeline_S2T_1 import TranscriptionPipeline
from src.pipeline_flagged_2 import FlaggedPipeline
from src.pipeline_intent_3 import IntentPipeline
from src.config import is_api_configured, OUTPUT_DIR, OUTPUT_FLAGGED_DIR, OUTPUT_INTENT_DIR

logger = logging.getLogger(__name__)

live_router = APIRouter()

TEMP_CHUNKS_DIR = BASE_DIR / "Live_Processing" / "temp_chunks"
TEMP_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

async def process_chunk(file_path: Path, websocket: WebSocket, chunk_id: str):
    """
    Background asynchronous processor for a single audio chunk.
    It runs the pipelines and sends the result back to the frontend.
    """
    try:
        if not is_api_configured():
            await websocket.send_json({"error": "Sarvam API Key is not configured in .env!"})
            return

        base_name = file_path.stem
        logger.info(f"Live processing chunk: {file_path.name}")

        # 1. S2T
        await websocket.send_json({"status": "processing", "message": f"Transcribing {file_path.name}..."})
        pipeline = TranscriptionPipeline()
        # Note: running this synchronously inside async will block the event loop, 
        # but for demonstration of the pipeline it's okay, or we can use asyncio.to_thread
        await asyncio.to_thread(
            pipeline.run_on_files,
            file_paths=[str(file_path)],
            language_code="unknown",  # Or gu-IN
            num_speakers=2,           # Expecting 2 speakers
            poll_interval_sec=5
        )

        processed_json_path = OUTPUT_DIR / f"{base_name}_processed.json"
        if not processed_json_path.exists():
            raise Exception(f"S2T failed for chunk, JSON not found: {processed_json_path}")

        # 2. Flagged
        await websocket.send_json({"status": "processing", "message": f"Extracting flagged keywords for {file_path.name}..."})
        flagged_pipeline = FlaggedPipeline()
        await asyncio.to_thread(flagged_pipeline.process_file, processed_json_path)

        flagged_json_path = OUTPUT_FLAGGED_DIR / f"flagged_{base_name}_processed.json"
        
        # 3. Intent
        await websocket.send_json({"status": "processing", "message": f"Detecting intent for {file_path.name}..."})
        intent_pipeline = IntentPipeline()
        await asyncio.to_thread(intent_pipeline.process_file, flagged_json_path)

        intent_json_path = OUTPUT_INTENT_DIR / f"intent_{base_name}_processed.json"

        # Read results
        with open(processed_json_path, 'r', encoding='utf-8') as f:
            audio_data = json.load(f)
        
        with open(intent_json_path, 'r', encoding='utf-8') as f:
            intent_data = json.load(f)

        result_payload = {
            "status": "completed",
            "chunk_id": chunk_id,
            "transcript_data": audio_data.get("segments", []),
            "intent_data": intent_data.get("segments", [])
        }
        
        # Send result back via WebSocket
        await websocket.send_json(result_payload)
        logger.info(f"Chunk {chunk_id} processed successfully.")

    except Exception as e:
        logger.error(f"Failed to process chunk {chunk_id}: {e}", exc_info=True)
        await websocket.send_json({"error": f"Chunk {chunk_id} failed: {str(e)}"})


@live_router.websocket("/api/live/ws")
async def live_audio_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established for Live Processing.")
    chunk_counter = 1

    try:
        while True:
            # Receive audio chunk as binary data from the frontend MediaRecorder
            data = await websocket.receive_bytes()
            
            chunk_id = f"chunk_{uuid.uuid4().hex[:8]}_{chunk_counter}"
            chunk_filename_webm = TEMP_CHUNKS_DIR / f"{chunk_id}.webm"
            chunk_filename_wav = TEMP_CHUNKS_DIR / f"{chunk_id}.wav"
            
            # Save the chunk
            with open(chunk_filename_webm, "wb") as f:
                f.write(data)
                
            # Convert WebM to WAV using ffmpeg to guarantee format compatibility for Sarvam
            # -y overwrites, -ar 16000 sets sample rate to 16kHz (optimal for ASR), -ac 1 sets to mono
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(chunk_filename_webm), "-ar", "16000", "-ac", "1", str(chunk_filename_wav)],
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
                
            logger.info(f"Received live audio chunk {chunk_counter} ({len(data)} bytes). Converted to {chunk_filename_wav}")
            
            # Fire and forget the processing task using the clean WAV file
            if chunk_filename_wav.exists():
                asyncio.create_task(process_chunk(chunk_filename_wav, websocket, chunk_id))
            else:
                logger.error(f"FFmpeg failed to convert chunk {chunk_id}. Using original WebM.")
                asyncio.create_task(process_chunk(chunk_filename_webm, websocket, chunk_id))
            
            chunk_counter += 1

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by the client.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

from fastapi.responses import FileResponse
from fastapi import HTTPException

@live_router.get("/api/live/audio/{chunk_id}")
async def get_live_audio(chunk_id: str):
    file_path = TEMP_CHUNKS_DIR / f"{chunk_id}.wav"
    if not file_path.exists():
        # Fallback to webm if wav conversion failed previously
        file_path = TEMP_CHUNKS_DIR / f"{chunk_id}.webm"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio chunk not found")
    return FileResponse(file_path)
