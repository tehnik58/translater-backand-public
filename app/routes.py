"""API endpoints for uploading/serving student audio records.

This module exposes endpoints for:
- listing student folders and available record dates
- returning a zip archive of a student's record set
- analyzing a student's record-by-record using an external AI service
- uploading a zip archive of new records along with metadata

The code is deliberately simple and designed to run with a local `records/` folder.
"""

import io
import json
import os
import re
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
import zipfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from config import settings
from DBController.db_router import SessionLocal, save_or_update_analysis
from openai import OpenAI

router = APIRouter()

# External AI service endpoint for audio analysis
AI_ANALYSIS_URL = settings.ai_analysis_url

# Root folder storing student recordings
RECORDS_DIR = settings.records_dir

# OpenAI client (configured via env OPENAI_API_KEY)
_openai_client: Optional[OpenAI] = None
if settings.openai_api_key:
    _openai_client = OpenAI(api_key=settings.openai_api_key)

# Default system prompt for analysis (aligned with the new server)
SYSTEM_PROMPT = (
    """
Ты — профессиональный преподаватель устного перевода, специализирующийся на подготовке студентов уровня B2–C1 к работе на научных конференциях.

Анализируешь устный двусторонний или последовательный перевод, выполненный в VR-сценарии.

Условия:
- Исходный текст предъявлялся устно.
- Перевод выполнялся без письменной опоры.
- Жанр: научная конференция.
- Требуется строгая терминологическая точность.
- Требуется сохранение академического регистра.
- Компрессия допустима только если полностью сохранён научный смысл и аргументация.
- Фонетику и интонацию не оценивай.
- Оба направления перевода оцениваются одинаково.

Работай в режиме экспертного отчёта для преподавателя.
Не обращайся к студенту напрямую.
Используй академический аналитический стиль.

Система оценивания:

Каждая реплика начинается с 10 баллов.
Применяется система штрафов.

−3 балла:
- полное искажение научного смысла;
- изменение субъектно-объектных отношений;
- нарушение причинно-следственной связи;
- утрата модальности (may → is и т.п.);
- серьёзная терминологическая ошибка;
- неверный перевод закреплённого научного или институционального термина.

−2 балла:
- частичное искажение (смысл в целом сохранён, но изменён оттенок, степень уверенности, временная форма с семантическим эффектом, тип стратегии);
- ослабление научной аргументации.

−1 балл:
- грамматическая ошибка, не искажающая смысл;
- регистровое снижение;
- стилистическая неточность;
- несущественная лексическая неточность;
- каждое самоисправление;
- техническая ошибка транскрипции, если она не влияет на терминологию.

Один и тот же тип ошибки не штрафуется повторно, если относится к одной смысловой проблеме.
Минимальный балл за реплику — 0.

Оценивай строго.
"""
)


def _file_ext(filename: str) -> str:
    return (Path(filename).suffix.lstrip(".") or "mp3").lower()


async def _analyze_with_openai(
    transcript: str,
    audio_bytes: bytes,
    audio_ext: str,
    system_prompt: Optional[str] = None,
) -> str:
    """Call OpenAI chat with base64 audio and transcript, return text answer."""
    if _openai_client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY не настроен на сервере")

    sp = system_prompt or SYSTEM_PROMPT
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    try:
        resp = _openai_client.chat.completions.create(
            model=settings.openai_model,
            modalities=["text"],
            audio={"voice": "alloy", "format": audio_ext},
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": sp}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Ты Эксперт по Лингвистике. Твоя задача сравнить аудио перевод "
                                f"студента с текстом - исходником. Текст: {transcript}"
                            ),
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_b64, "format": audio_ext},
                        },
                    ],
                },
            ],
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Ошибка OpenAI: {e}")

class EducationData(BaseModel):
    """A minimal schema for metadata.json that describes a student's recording session."""

    scena: str
    data: List[str]

def _ensure_dir_exists(path: Path) -> None:
    """Create a directory if it does not already exist."""

    path.mkdir(parents=True, exist_ok=True)


def _get_student_folder(student_name: str) -> Path:
    return RECORDS_DIR / student_name


def _get_student_date_folder(student_name: str, date: str) -> Path:
    return _get_student_folder(student_name) / date


def get_student_hierarhy() -> Dict[str, List[str]]:
    """Return a list of students and their available record dates."""

    students = [p.name for p in RECORDS_DIR.iterdir() if p.is_dir()]
    hierarchy = {
        s: [d.name for d in (_get_student_folder(s)).iterdir() if d.is_dir()]
        for s in students
    }

    return {"students": students, "students_hierarhy": hierarchy}

def _zip_folder_to_bytes(folder: Path) -> io.BytesIO:
    """Archive a folder into an in-memory ZIP file."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(folder):
            for filename in files:
                full_path = Path(root) / filename
                zf.write(full_path, full_path.relative_to(folder))

    buffer.seek(0)
    return buffer

def _read_metadata(student_name: str, date: str) -> EducationData:
    """Read metadata.json and validate it against the schema."""

    metadata_path = _get_student_date_folder(student_name, date) / "metadata.json"
    with metadata_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return EducationData(**raw)


def _sorted_audio_paths(base_folder: Path) -> List[Path]:
    """Return a sorted list of audio file paths from the source_audio folder."""

    def _sort_key(path: Path) -> int:
        numbers = re.findall(r"\d+", path.name)
        return int(numbers[0]) if numbers else 0

    source_folder = base_folder / "source_audio"
    return sorted(source_folder.iterdir(), key=_sort_key)


def _build_marked_data(student_name: str, date: str) -> List[str]:
    """Return `metadata.data` where each item is replaced by a marked audio file path.

    Example output:
        ["Привет", "*records/student/2026-.../source_audio/1.mp3*", ...]
    """

    metadata = _read_metadata(student_name, date)
    audio_paths = _sorted_audio_paths(_get_student_date_folder(student_name, date))

    for audio_path in audio_paths:
        index = int(audio_path.stem) - 1
        if 0 <= index < len(metadata.data):
            metadata.data[index] = f"*{audio_path.as_posix()}*"

    return metadata.data

#=======================================================================================

@router.post("/students_hierarhy")
async def students_hierarhy():
    return get_student_hierarhy()
#=======================================================================================

@router.post("/student_records")
async def student_records(student: str, date: str) -> StreamingResponse:
    """Download the student record folder as a ZIP archive."""

    _read_metadata(student, date)  # validate metadata exists

    zip_bytes = _zip_folder_to_bytes(_get_student_date_folder(student, date))
    return StreamingResponse(
        zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={student}.zip"},
    )
#=======================================================================================
def _write_answers_csv(answers: Dict[str, List[str]], filename: str = "analysis.csv") -> None:
    """Persist analysis results into a CSV file."""

    import csv

    fieldnames = ["original", "answer"]
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for original, answer in zip(answers["original"], answers["answers"]):
            writer.writerow({"original": original, "answer": answer})


@router.post("/student_analize_record")
async def student_analyze_record(name: str, date: str) -> Dict[str, List[str]]:
    """Analyze student recordings with OpenAI using transcript+audio pairs, then store results."""

    marked_data = _build_marked_data(name, date)

    # Each record uses two consecutive entries: [text, *audio_path*]
    pairs = list(zip(marked_data[::2], marked_data[1::2]))

    db = SessionLocal()
    answers: Dict[str, List[str]] = {"original": [], "answers": []}

    for prompt, marked_audio in pairs:
        audio_path = Path(marked_audio.replace("*", ""))
        audio_ext = _file_ext(audio_path.name)

        try:
            audio_bytes = audio_path.read_bytes()
            result_text = await _analyze_with_openai(prompt, audio_bytes, audio_ext)

            save_or_update_analysis(
                db=db,
                name=name,
                date=date,
                original_text=prompt,
                ai_answer=result_text,
            )

            answers["original"].append(prompt)
            answers["answers"].append(result_text)

            _write_answers_csv(answers)

        except HTTPException as exc:
            # Already normalized HTTPException (e.g., OpenAI error or config missing)
            raise exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Ошибка анализа записи: {exc}")

    db.commit()
    db.close()

    return answers
#=======================================================================================

@router.post("/student_analyze_single")
async def student_analyze_single(
    file: UploadFile = File(..., description="Аудиозапись студента"),
    language: str = Form(..., description="Язык речи студента (например, ru, en)"),
    transcript: str = Form(..., description="Текст расшифровки аудиозаписи")
) -> Dict[str, object]:
    """Проверить одну запись студента через ИИ вместе с расшифровкой.

    Принимает только три параметра: аудиофайл, язык и текст расшифровки.
    Возвращает ответ ИИ без сохранения в БД.
    """

    try:
        contents = await file.read()
        ext = _file_ext(file.filename or "audio.mp3")

        result_text = await _analyze_with_openai(transcript, contents, ext)

        return {
            "language": language,
            "transcript": transcript,
            "answer": result_text,
        }

    except HTTPException:
        raise
    except Exception as exc:  # Защита от неожиданных ошибок чтения файла и т.п.
        raise HTTPException(status_code=400, detail=f"Ошибка обработки запроса: {exc}")

#=======================================================================================

@router.post("/upload_records")
async def upload_records(
    data: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        json_data = json.loads(data)
        education_data = EducationData(**json_data)
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=400, detail="Некорректный формат JSON в поле data")
    
    # NOTE: debug output; remove or replace with structured logging as needed
    # print(education_data)

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Разрешены только .zip файлы")

    contents = await file.read()
    try:
        # Используем io.BytesIO, чтобы работать с содержимым как с файлом в памяти
        with zipfile.ZipFile(io.BytesIO(contents)) as z:
            # Получаем список файлов внутри архива
            file_list = z.namelist()

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            student_folder = RECORDS_DIR / Path(file.filename).stem / timestamp

            destination_audio = student_folder / "source_audio"
            _ensure_dir_exists(destination_audio)

            z.extractall(destination_audio)

            metadata_path = student_folder / "metadata.json"

            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump(education_data.model_dump(), f, ensure_ascii=False, indent=4)

            return {
                "filename": file.filename,
                "files_inside": file_list,
                "status": "Архив успешно прочитан"
            }
        
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Некорректный zip-архив")