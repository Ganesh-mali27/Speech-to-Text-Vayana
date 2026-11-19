# Speech-to-Text Trade Surveillance

A speech-to-text processing system developed for **trade surveillance**, converting recorded audio conversations into text transcripts and identifying potentially relevant trading terms for downstream review.

## Overview

The project explores how speech recognition can support compliance-oriented workflows by transforming audio conversations into structured text that can be further analysed for potentially relevant trading terminology.

The system contains components for audio processing, speech-to-text conversion, backend API handling, and a frontend interface for interacting with the processing workflow.

## Key Features

- 🎙️ **Speech-to-Text** — Converts audio conversations into text transcripts.
- 🔎 **Trading Term Detection** — Identifies predefined words or phrases relevant to trading surveillance.
- ⚙️ **Backend API** — Provides backend services for processing and handling transcription requests.
- 🖥️ **Frontend Interface** — Provides an interface for interacting with the transcription workflow.
- 📁 **Audio Processing** — Supports working with stored audio files and live-processing components.
- 🔄 **Modular Structure** — Separates frontend, backend, live processing, and core source components.

## System Workflow

```text
Audio Input
    ↓
Audio Processing
    ↓
Speech-to-Text
    ↓
Generated Transcript
    ↓
Trading Term Detection
    ↓
Flagged Terms / Review
```

## Project Structure

```text
Speech-to-Text-Vayana/
│
├── Audios/            # Audio files used for processing
├── Live_Processing/   # Components related to live audio processing
├── backend/           # Backend/API implementation
├── frontend/          # Frontend interface
├── src/               # Core source code
├── requirements.txt   # Python dependencies
├── run_system.txt     # System execution instructions
└── README.md          # Project documentation
```

## Technology Stack

- **Python**
- **Speech-to-Text / Speech Recognition**
- **FastAPI**
- **REST APIs**
- **Audio Processing**
- **Frontend Web Technologies**
- **Git / GitHub**

## Running the Project

### 1. Clone the repository

```bash
git clone https://github.com/Ganesh-mali27/Speech-to-Text-Vayana.git
cd Speech-to-Text-Vayana
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

The current project dependencies include FastAPI, Uvicorn, Requests, python-dotenv, and python-multipart. 

### 4. Configure environment variables

If API credentials or configuration values are required, create a `.env` file and add the required values.

**Do not commit API keys or other secrets to GitHub.**

### 5. Run the application

Follow the execution instructions provided in `run_system.txt` for the relevant backend/frontend or live-processing components.

## Project Focus

This project was developed as part of practical work in **speech processing and AI-assisted trade surveillance**.

The main focus was on connecting speech-to-text processing with a downstream review workflow rather than treating transcription as an isolated task.

## Future Improvements

Potential extensions include:

- Benchmarking transcription accuracy using Word Error Rate (WER)
- Comparing different speech recognition models
- Evaluating transcription quality under noisy audio conditions
- Measuring processing latency
- Adding confidence-based flagging
- Supporting additional languages
- Extending the workflow toward real-time speech interaction

## Author

**Ganesh Mali**

M.Sc. Data Science | AI/ML

[GitHub](https://github.com/Ganesh-mali27)
