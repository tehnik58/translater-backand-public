import json
import os
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from typing import List
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, ValidationError
from fastapi.concurrency import run_in_threadpool
from datetime import datetime
from openai import OpenAI
import base64
import zipfile
import io
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

client = OpenAI(
    api_key=""
)

system_prompt="""
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

router = APIRouter()

async def ask_gpt(txt, file:UploadFile, system_prompt=None, model: str = None):
    if system_prompt is None:
        system_prompt = """
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
    if model is None:
        model = "gpt-audio-mini-2025-12-15"
    print(f".{file.filename.split('.')[1]}")
    audio_bytes = await file.read()
    # 2. Кодируем байты в base64 строку
    audio_data_b64 = base64.b64encode(audio_bytes).decode('utf-8')
    try:
        # 2. Отправка запроса
        response = client.chat.completions.create(
            model=model,
            modalities=["text"],

            audio={"voice": "alloy", "format": f"{file.filename.split('.')[1]}"},
            messages=[
                    {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system_prompt
                        }
                    ]
                    },
                    {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": f"Ты Эксперт по Лингвистике. Твоя задача сравнить аудио перевод студента с текстом - исходником. Текст: {txt}"
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_data_b64,
                                "format": f"{file.filename.split('.')[1]}"
                            }
                        }
                    ]
                    }
            ]
        )
        
        # 3. Получение текста ответа
        return response.choices[0].message.content

    except Exception as e:
        return f"Произошла ошибка: {e}"
    
class EducationData(BaseModel):
    scena: str
    data: List[str]

@router.get("/transcribe", response_class=HTMLResponse)
async def get_transcribe(request: Request):
    return templates.TemplateResponse("transcribe.html", {"request": request})

@router.post("/transcribe", response_class=HTMLResponse)
async def post_transcribe(request: Request, file: UploadFile = File(...), language: str = Form(...)):
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse("transcribe.html", {"request": request, "error": f"Неподдерживаемый формат. Допустимы: {', '.join(ALLOWED_EXTENSIONS)}"})
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return templates.TemplateResponse("transcribe.html", {"request": request, "error": "Файл слишком большой (макс. 25 МБ)"})
    try:
        from io import BytesIO
        file_obj = BytesIO(content)
        file_obj.name = f"upload.{ext}"
        transcription = await run_in_threadpool(
            client.audio.transcriptions.create,
            model="whisper-1",
            file=file_obj,
            language=language,
            response_format="text"
        )
        return templates.TemplateResponse("transcribe.html", {"request": request, "result": transcription})
    except Exception as e:
        return templates.TemplateResponse("transcribe.html", {"request": request, "error": f"Ошибка транскрибации: {str(e)}"})

@router.get("/analyze", response_class=HTMLResponse)
async def get_analyze(request: Request):
    default_system = """
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
    return templates.TemplateResponse("analyze.html", {"request": request, "system_prompt": default_system, "gpt_version": "gpt-audio-mini-2025-12-15"})

@router.post("/analyze", response_class=HTMLResponse)
async def post_analyze(request: Request, system_prompt: str = Form(...), user_prompt: str = Form(...), gpt_version: str = Form(...), file: UploadFile = File(...)):
    output = await ask_gpt(user_prompt, file, system_prompt, gpt_version)
    return templates.TemplateResponse("analyze.html", {"request": request, "result": output, "system_prompt": system_prompt, "user_prompt": user_prompt, "gpt_version": gpt_version})

ALLOWED_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB (лимит API)

@router.post("/spech_to_text")
async def spech_to_text(
    file: UploadFile = File(...)
):
    # 1. Валидация расширения
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат. Допустимы: {', '.join(ALLOWED_EXTENSIONS)}")

    # 2. Чтение и проверка размера
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 25 МБ)")
    
    # 3. Вызов API (в пуле потоков, чтобы не блокировать асинхронность)
    try:
        from io import BytesIO
        file_obj = BytesIO(content)
        file_obj.name = f"upload.{ext}"  # Whisper требует имя файла

        # Переходим в поток для синхронного вызова SDK
        transcription = await run_in_threadpool(
            client.audio.transcriptions.create,
            model="gpt-4o-transcribe",
            file=file_obj,
            response_format="text"
        )
        
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка транскрибации: {str(e)}")

# -----------------------------
# Новые эндпоинты и страницы
# -----------------------------

@router.get("/ask", response_class=HTMLResponse)
async def get_ask(request: Request):
    default_system = "Вы — полезный ассистент. Отвечайте кратко и по делу."
    default_model = "gpt-4o-mini"
    return templates.TemplateResponse("ask.html", {"request": request, "system_prompt": default_system, "model": default_model})

@router.post("/ask", response_class=HTMLResponse)
async def post_ask(request: Request, system_prompt: str = Form(...), user_prompt: str = Form(...), model: str = Form(...)):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = response.choices[0].message.content
        return templates.TemplateResponse("ask.html", {"request": request, "system_prompt": system_prompt, "user_prompt": user_prompt, "model": model, "result": answer})
    except Exception as e:
        return templates.TemplateResponse("ask.html", {"request": request, "system_prompt": system_prompt, "user_prompt": user_prompt, "model": model, "error": f"Ошибка запроса к модели: {str(e)}"})

@router.get("/transcribe_model", response_class=HTMLResponse)
async def get_transcribe_model(request: Request):
    return templates.TemplateResponse("transcribe_model.html", {"request": request, "model": "whisper-1"})

@router.post("/transcribe_model", response_class=HTMLResponse)
async def post_transcribe_model(request: Request, file: UploadFile = File(...), model: str = Form(...)):
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse("transcribe_model.html", {"request": request, "model": model, "error": f"Неподдерживаемый формат. Допустимы: {', '.join(ALLOWED_EXTENSIONS)}"})
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return templates.TemplateResponse("transcribe_model.html", {"request": request, "model": model, "error": "Файл слишком большой (макс. 25 МБ)"})
    try:
        from io import BytesIO
        file_obj = BytesIO(content)
        file_obj.name = f"upload.{ext}"
        transcription = await run_in_threadpool(
            client.audio.transcriptions.create,
            model=model,
            file=file_obj,
            response_format="text",
        )
        return templates.TemplateResponse("transcribe_model.html", {"request": request, "model": model, "result": transcription})
    except Exception as e:
        return templates.TemplateResponse("transcribe_model.html", {"request": request, "model": model, "error": f"Ошибка транскрибации: {str(e)}"})