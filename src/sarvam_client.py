import os
import requests
import logging
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SarvamClient:
    def __init__(self, api_key: str, base_url: str = "https://api.sarvam.ai"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }

    def create_job(
        self,
        language_code: str = "unknown",
        with_diarization: bool = True,
        num_speakers: Optional[int] = None,
        model: str = "saaras:v3"
    ) -> Dict[str, Any]:
        """
        Initiate a batch Speech-to-Text job.
        """
        url = f"{self.base_url}/speech-to-text/job/v1"
        
        job_params = {
            "model": model,
            "mode": "transcribe",
            "language_code": language_code,
            "with_diarization": with_diarization,
            "with_timestamps": True  # Explicitly enable timestamps to get segment details
        }
        
        if num_speakers is not None:
            job_params["num_speakers"] = num_speakers

        payload = {
            "job_parameters": job_params
        }

        logger.info(f"Initiating STT batch job with params: {job_params}")
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Batch job initiated. Job ID: {data.get('job_id')}")
        return data

    def get_upload_urls(self, job_id: str, filenames: List[str]) -> Dict[str, str]:
        """
        Request presigned upload URLs for a list of audio filenames.
        """
        url = f"{self.base_url}/speech-to-text/job/v1/upload-files"
        payload = {
            "job_id": job_id,
            "files": filenames
        }

        logger.info(f"Requesting upload URLs for job {job_id} and files {filenames}")
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        parsed_urls = {}
        # Parse response keys: 'upload_urls' or 'urls'
        raw_urls = data.get("upload_urls", data.get("urls", {}))
        
        if isinstance(raw_urls, dict):
            for name, val in raw_urls.items():
                if isinstance(val, dict):
                    # Nesting like {"file.wav": {"file_url": "https://..."}}
                    u_url = val.get("file_url") or val.get("url") or val.get("upload_url")
                    if u_url:
                        parsed_urls[name] = u_url
                elif isinstance(val, str):
                    parsed_urls[name] = val
        elif isinstance(raw_urls, list):
            for item in raw_urls:
                if isinstance(item, dict):
                    name = item.get("file_name") or item.get("filename")
                    u_url = item.get("file_url") or item.get("upload_url") or item.get("url")
                    if isinstance(u_url, dict):
                        u_url = u_url.get("file_url") or u_url.get("url")
                    if name and u_url:
                        parsed_urls[name] = u_url
                        
        logger.info(f"Successfully retrieved upload URLs for {list(parsed_urls.keys())}")
        return parsed_urls

    def upload_file(self, upload_url: str, file_path: str) -> None:
        """
        Upload binary audio file to the presigned upload URL using HTTP PUT.
        """
        logger.info(f"Uploading {os.path.basename(file_path)} to storage container...")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        # Determine Content-Type based on extension
        content_type = "audio/wav"
        if file_path.lower().endswith(".mp3"):
            content_type = "audio/mpeg"
        elif file_path.lower().endswith(".ogg"):
            content_type = "audio/ogg"

        with open(file_path, "rb") as f:
            file_data = f.read()

        # Azure/GCS presigned URLs usually use PUT request.
        # Azure Blob Storage requires the x-ms-blob-type header for block blob uploads.
        put_headers = {
            "Content-Type": content_type,
            "x-ms-blob-type": "BlockBlob"
        }
        
        response = requests.put(upload_url, data=file_data, headers=put_headers)
        response.raise_for_status()
        logger.info(f"Successfully uploaded {os.path.basename(file_path)}")

    def start_job(self, job_id: str) -> Dict[str, Any]:
        """
        Trigger the processing of the batch job after files are uploaded.
        """
        url = f"{self.base_url}/speech-to-text/job/v1/{job_id}/start"
        logger.info(f"Starting ASR batch processing for job: {job_id}")
        
        response = requests.post(url, headers=self.headers, json={})
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"ASR job start request accepted. State: {data.get('job_state')}")
        return data

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Retrieve the current status of the batch job.
        """
        url = f"{self.base_url}/speech-to-text/job/v1/{job_id}/status"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()

    def download_results(self, job_id: str, filenames: List[str]) -> Dict[str, Any]:
        """
        Download the finished transcription output files and return their parsed contents.
        """
        url = f"{self.base_url}/speech-to-text/job/v1/download-files"
        payload = {
            "job_id": job_id,
            "files": filenames
        }

        logger.info(f"Requesting download URLs for files: {filenames}")
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # Support dict mapping file -> URL, or list of dicts with file_name and download_url
        raw_urls = data.get("download_urls", data.get("urls", {}))
        download_urls = {}
        
        if isinstance(raw_urls, dict):
            for name, val in raw_urls.items():
                if isinstance(val, dict):
                    d_url = val.get("file_url") or val.get("url") or val.get("download_url")
                    if d_url:
                        download_urls[name] = d_url
                elif isinstance(val, str):
                    download_urls[name] = val
        elif isinstance(raw_urls, list):
            for item in raw_urls:
                if isinstance(item, dict):
                    name = item.get("file_name") or item.get("filename")
                    d_url = item.get("file_url") or item.get("download_url") or item.get("url")
                    if isinstance(d_url, dict):
                        d_url = d_url.get("file_url") or d_url.get("url")
                    if name and d_url:
                        download_urls[name] = d_url

        downloaded_contents = {}
        for name, d_url in download_urls.items():
            logger.info(f"Downloading result for file {name}...")
            res = requests.get(d_url)
            res.raise_for_status()
            downloaded_contents[name] = res.json()
            
        return downloaded_contents

    def transliterate(
        self,
        text: str,
        source_language_code: str,
        target_language_code: str = "en-IN"
    ) -> str:
        """
        Transliterate text from source Indic script to target (default: en-IN / Roman script).
        """
        # Truncate to maximum allowed characters if necessary
        if len(text) > 1000:
            logger.warning("Input text exceeds 1000 characters. Truncating for transliteration.")
            text = text[:1000]

        url = f"{self.base_url}/transliterate"
        payload = {
            "input": text,
            "source_language_code": source_language_code,
            "target_language_code": target_language_code
        }

        response = requests.post(url, headers=self.headers, json=payload)
        
        # Fail gracefully without crashing the whole pipeline if transliteration errors
        try:
            response.raise_for_status()
            data = response.json()
            return data.get("transliterated_text", text)
        except Exception as e:
            logger.error(f"Transliteration failed for text '{text[:30]}...': {e}")
            if response.text:
                logger.error(f"Transliterate error response: {response.text}")
            return text
