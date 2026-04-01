import requests
from config import settings
import json
import logging
import time

logger = logging.getLogger(__name__)


def transcribe_via_api(file_bytes: bytes, filename: str) -> str:
    url = settings.ai_analysis_url.rstrip("/") + "/api/v1/spech_to_text"
    try:
        t0 = time.perf_counter()
        logger.info("Transcribe request -> %s (%s)", url, filename)
        files = {"file": (filename, file_bytes)}
        resp = requests.post(url, files=files, timeout=30)
        resp.raise_for_status()
        logger.debug("Transcribe response: status=%s, content_type=%s", resp.status_code, resp.headers.get("Content-Type"))
        if "application/json" in resp.headers.get("Content-Type", ""):
            data = resp.json()
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("Transcribe ok: text_len=%d, took=%.1f ms", len(data.get("text") or data.get("transcript") or ""), elapsed)
            return data.get("text") or data.get("transcript") or ""
        text = resp.text
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Transcribe ok (text): len=%d, took=%.1f ms", len(text), elapsed)
        return text
    except Exception as e:
        logger.exception("Transcribe failed: %s", e)
        return ""


def analyze_via_api(transcript: str, original: str) -> str:
    # Send transcript as a text query to the external service using the /ask endpoint.
    url = settings.ai_analysis_url.rstrip("/") + "/api/v1/ask"
    system_prompt = settings.system_prompt
    # Include both original source text (ST) and student's transcript (TT)
    user_prompt = f"Original:\n{original}\n\nTranslate:\n{transcript}"
    # FastAPI /ask expects 'model' form field, not 'gpt_version'
    data = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "model": settings.ai_model or "gpt-4o-mini",
    }
    import re
    try:
        t0 = time.perf_counter()
        logger.info("Analyze request -> %s (transcript_len=%d, original_len=%d)", url, len(transcript or ""), len(original or ""))
        resp = requests.post(url, data=data, timeout=60)
        resp.raise_for_status()
        logger.debug("Analyze response: status=%s, content_type=%s", resp.status_code, resp.headers.get("Content-Type"))
        if "application/json" in resp.headers.get("Content-Type", ""):
            j = resp.json()
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("Analyze ok (json): keys=%s, took=%.1f ms", list(j.keys()), elapsed)
            return j.get("answer") or j.get("response") or j.get("result") or json.dumps(j)
        # Extract plain text from <pre>...</pre> if exists, else return as is
        text = resp.text
        match = re.search(r'<pre>(.*?)</pre>', text, re.DOTALL)
        if match:
            out = match.group(1).strip()
        else:
            out = text
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Analyze ok (text): len=%d, took=%.1f ms", len(out), elapsed)
        return out
    except Exception as e:
        logger.exception("Analyze failed: %s", e)
        return ""
