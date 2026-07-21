# pyrefly: ignore [missing-import]
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
import shutil
import json
from pathlib import Path
import sys
import logging

# Setup paths to import from src
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.config import AUDIO_DIR, OUTPUT_DIR, OUTPUT_FLAGGED_DIR, OUTPUT_INTENT_DIR, is_api_configured
from src.pipeline_S2T_1 import TranscriptionPipeline
from src.pipeline_flagged_2 import FlaggedPipeline
from src.pipeline_intent_3 import IntentPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Below is Live Part code ---
from Live_Processing.backend_live.live_api import live_router
# --- Live part code ends ---

app = FastAPI(title="Vayana Voice API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks = {} # In-memory store for task status

def process_audio(task_id: str, file_path: Path):
    tasks[task_id] = {"status": "processing", "message": "Starting S2T pipeline..."}
    try:
        if not is_api_configured():
            raise Exception("Sarvam API Key is not configured in .env!")

        base_name = file_path.stem
        logger.info(f"Task {task_id}: Processing {file_path.name}")

        # 1. S2T
        tasks[task_id]["message"] = "Transcribing audio..."
        pipeline = TranscriptionPipeline()
        pipeline.run_on_files(
            file_paths=[str(file_path)],
            language_code="unknown",
            num_speakers=None,
            poll_interval_sec=5
        )

        processed_json_path = OUTPUT_DIR / f"{base_name}_processed.json"
        if not processed_json_path.exists():
             raise Exception(f"S2T failed, JSON not found: {processed_json_path}")

        # 2. Flagged
        tasks[task_id]["message"] = "Extracting flagged keywords..."
        flagged_pipeline = FlaggedPipeline()
        flagged_pipeline.process_file(processed_json_path)

        flagged_json_path = OUTPUT_FLAGGED_DIR / f"flagged_{base_name}_processed.json"
        if not flagged_json_path.exists():
             raise Exception(f"Flagged extraction failed, JSON not found: {flagged_json_path}")

        # 3. Intent
        tasks[task_id]["message"] = "Detecting intent..."
        intent_pipeline = IntentPipeline()
        intent_pipeline.process_file(flagged_json_path)

        intent_json_path = OUTPUT_INTENT_DIR / f"intent_{base_name}_processed.json"
        if not intent_json_path.exists():
            raise Exception(f"Intent detection failed, JSON not found: {intent_json_path}")

        # Read results
        with open(processed_json_path, 'r', encoding='utf-8') as f:
            audio_data = json.load(f)
        
        with open(intent_json_path, 'r', encoding='utf-8') as f:
            intent_data = json.load(f)

        tasks[task_id] = {
            "status": "completed",
            "audio_filename": file_path.name,
            "transcript_data": audio_data.get("segments", []),
            "intent_data": intent_data.get("segments", [])
        }
        logger.info(f"Task {task_id}: Completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        tasks[task_id] = {"status": "failed", "message": str(e)}


@app.post("/api/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    file_path = AUDIO_DIR / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    tasks[task_id] = {"status": "pending", "message": "File uploaded, pending processing..."}
    background_tasks.add_task(process_audio, task_id, file_path)

    return {"task_id": task_id}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    file_path = AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path)

# Serve static files for frontend
frontend_dir = BASE_DIR / "frontend"
frontend_dir.mkdir(parents=True, exist_ok=True)

# --- Below is Live Part code ---
# Also mount the live frontend files so we can serve live_script.js
app.mount("/live_scripts", StaticFiles(directory=str(BASE_DIR / "Live_Processing" / "frontend_live")), name="live_scripts")
app.include_router(live_router)
# --- Live part code ends ---

app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
