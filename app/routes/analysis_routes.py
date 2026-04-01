from fastapi import APIRouter, File, Query, UploadFile, Form, HTTPException
import os
import time
import json
import logging

from config import settings
from ai_client import transcribe_via_api, analyze_via_api
from DBController.db_router import insert_analysis_result, delete_analysis_results_for_date


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/student_analize_record")
def student_analize_record(name: str= Form(...), date: str = Form(...)):
    t0 = time.perf_counter()
    logger.info("Batch analysis start: student=%s, date=%s", name, date)
    # Batch analyze audio files under records/<name>/<date>/source_audio
    base = os.path.join(settings.records_dir, name, date, "source_audio")
    meta_path = os.path.join(settings.records_dir, name, date, "metadata.json")
    if not os.path.exists(base) or not os.path.isdir(base):
        logger.warning("Record folder not found for student=%s date=%s", name, date)
        raise HTTPException(status_code=404, detail="Record folder not found")

    # Load metadata to preserve the exact order specified in JSON (field 'data')
    try:
        with open(meta_path, "r", encoding="utf-8") as mf:
            metadata = json.load(mf)
        data_items = metadata.get("data", [])
        items_count = len(data_items)
        logger.info("Loaded metadata with %d items from %s", items_count, meta_path)
    except Exception:
        # Fallback: if no metadata, use discovered files (sorted by numeric prefix if possible)
        metadata = {"data": []}
        data_items = []
        items_count = 0
        logger.info("No valid metadata found at %s; falling back to discovered files", meta_path)

    # Ensure previous results for this student/date are replaced, not duplicated
    try:
        delete_analysis_results_for_date(name, date)
        logger.debug("Cleared previous analysis results for %s %s", name, date)
    except Exception as e:
        logger.warning("Failed to clear previous results for %s %s: %s", name, date, e)

    # Prepare mapping from index -> filename by numeric prefix (e.g., 1.mp3 -> 1)
    files = [f for f in os.listdir(base) if os.path.isfile(os.path.join(base, f))]
    indexed = {}
    for f in files:
        prefix = f.split(".")[0]
        if prefix.isdigit():
            idx = int(prefix)
            # keep the first occurrence per index
            indexed.setdefault(idx, f)

    processed = []

    def process_one(fname: str, original_text: str):
        fpath = os.path.join(base, fname)
        try:
            with open(fpath, "rb") as fh:
                content = fh.read()
        except Exception as e:
            logger.error("Failed to read file %s: %s", fpath, e)
            return None
        logger.debug("Read %d bytes from %s", len(content) if content else 0, fpath)
        transcript = transcribe_via_api(content, fname) or ""
        logger.info("Transcribed %s: length=%d", fname, len(transcript))
        ai_answer = analyze_via_api(transcript, original_text) or "" if transcript else ""
        if transcript:
            logger.info("Analyzed %s: answer_length=%d", fname, len(ai_answer))
        try:
            # Store the original ST text and the AI answer in DB, preserving order
            insert_analysis_result(name, date, json.dumps([original_text]), json.dumps([ai_answer]))
        except Exception as e:
            logger.warning("DB insert failed for %s %s %s: %s", name, date, fname, e)
        processed.append({"file": fname, "transcript": transcript, "ai_answer_present": bool(ai_answer)})
        logger.debug("Processed file %s; transcript+original logged at DEBUG", fname)

    if items_count > 0:
        # Follow the exact order from metadata 'data': process only odd positions (1-based),
        # mapping to audio files named with the next even index (e.g., 1->2, 3->4, ...)
        for i in range(1, items_count + 1, 2):
            original_text = data_items[i - 1] if (i - 1) < items_count else ""
            audio_index = i + 1  # expected audio file numeric prefix
            fname = indexed.get(audio_index)
            if fname:
                process_one(fname, original_text)
            else:
                # No corresponding file for this original; skip
                logger.debug("No audio file for expected index %d", audio_index)
                continue
    else:
        # No metadata — process discovered files in a stable deterministic order
        for fname in sorted(files):
            process_one(fname, "")

    elapsed = (time.perf_counter() - t0) * 1000
    logger.info("Batch analysis done: student=%s, date=%s, files=%d, took=%.1f ms", name, date, len(processed), elapsed)
    return {"student": name, "date": date, "processed": processed}


@router.post("/student_analyze_single")
async def student_analyze_single(file: UploadFile = File(...), language: str = Form(...), transcript: str = Form(None), student: str | None = Form(None)):
    # Analyze a single uploaded file (or provided transcript). Results saved to DB.
    logger.info("Single analysis upload: filename=%s, language=%s, student=%s", file.filename, language, student)
    try:
        content = await file.read()
    except Exception as e:
        logger.error("Failed to read uploaded file %s: %s", file.filename, e)
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    if transcript:
        text = transcript
    else:
        text = transcribe_via_api(content, file.filename) or ""

    ai_answer = ""
    if text:
        ai_answer = analyze_via_api(text, "") or ""
    logger.info("Single analysis result: transcript_len=%d, answer_len=%d", len(text) if text else 0, len(ai_answer) if ai_answer else 0)

    student_name = student or file.filename or "unknown"
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    try:
        insert_analysis_result(student_name, timestamp, json.dumps([text]), json.dumps([ai_answer]))
    except Exception as e:
        logger.warning("DB insert failed for single analysis %s %s: %s", student_name, timestamp, e)

    return {"student": student_name, "date": timestamp, "transcript": text, "ai_answer": ai_answer}
