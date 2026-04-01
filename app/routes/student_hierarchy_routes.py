from fastapi import APIRouter, HTTPException
import os

import urllib
from config import settings
from fastapi.responses import StreamingResponse
import io
import zipfile
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/students_hierarhy")
def students_hierarhy():
    base = settings.records_dir
    students = []
    hierarchy = {}
    if not os.path.exists(base):
        logger.info("Records directory not found: %s", base)
        return {"students": [], "students_hierarhy": {}}
    for student in sorted(os.listdir(base)):
        student_path = os.path.join(base, student)
        if os.path.isdir(student_path):
            dates = sorted([d for d in os.listdir(student_path) if os.path.isdir(os.path.join(student_path, d))])
            students.append(student)
            hierarchy[student] = dates
    logger.info("Hierarchy listed: %d students", len(students))
    return {"students": students, "students_hierarhy": hierarchy}


@router.post("/student_records")
def student_records(student: str, date: str):
    base = settings.records_dir
    target = os.path.join(base, student, date)
    if not os.path.exists(target):
        logger.warning("Student records not found: %s / %s", student, date)
        raise HTTPException(status_code=404, detail="Not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(target):
            for f in files:
                path = os.path.join(root, f)
                arcname = os.path.relpath(path, target)
                z.write(path, arcname)
    buf.seek(0)
    logger.info("Student records zipped: %s / %s", student, date)
    #return StreamingResponse(buf, media_type="application/x-zip-compressed", headers={"Content-Disposition": f"attachment; filename={student}_{date}.zip"})

    filename_encoded = urllib.parse.quote(f"{student}_{date}.zip", encoding='utf-8')
    content_disposition = f"attachment; filename=\"{filename_encoded}\"; filename*=UTF-8"

    return StreamingResponse(
        buf, 
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": content_disposition}
    )
