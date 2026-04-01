from fastapi import APIRouter, File, UploadFile, Form, HTTPException
import json
import zipfile
import os
import time
import logging

from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload_records")
async def upload_records(data: str = Form(...), file: UploadFile = File(...), student: str | None = Form(None)):
    print(f"student: {student}")
    start = time.perf_counter()
    logger.info("Upload started: filename=%s, content_type=%s, student(form)=%s", file.filename, getattr(file, 'content_type', None), student)
    try:
        metadata = json.loads(data)
    except Exception:
        logger.warning("Invalid JSON in 'data' field during upload of %s", file.filename)
        raise HTTPException(status_code=400, detail="Invalid JSON in 'data' field")
    print(f"student: {metadata.get("student")}")
    student_name = student or metadata.get("student") or "unknown"
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    base_dir = os.path.join(settings.records_dir, student_name, timestamp)
    source_dir = os.path.join(base_dir, "source_audio")
    os.makedirs(source_dir, exist_ok=True)

    # save metadata
    with open(os.path.join(base_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)

    # save uploaded file temporarily and extract
    tmp_path = os.path.join(base_dir, file.filename)
    content = await file.read()
    logger.debug("Read uploaded file bytes: size=%d", len(content) if content else 0)
    with open(tmp_path, "wb") as f:
        f.write(content)

    try:
        with zipfile.ZipFile(tmp_path) as z:
            z.extractall(source_dir)
            files_inside = z.namelist()
            logger.info("Zip extracted to %s with %d files", source_dir, len(files_inside))
    except zipfile.BadZipFile:
        logger.error("Uploaded file is not a valid zip archive: %s", tmp_path)
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid zip archive")
    finally:
        try:
            os.remove(tmp_path)
            logger.debug("Temporary file removed: %s", tmp_path)
        except Exception:
            logger.debug("Failed to remove temporary file: %s", tmp_path)

    elapsed = (time.perf_counter() - start) * 1000
    logger.info("Upload completed: student=%s, date=%s, files=%d, took=%.1f ms", student_name, timestamp, len(files_inside), elapsed)
    return {"filename": file.filename, "files_inside": files_inside, "status": "ok", "student": student_name, "date": timestamp}
