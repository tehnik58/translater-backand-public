# Training Server — бэкенд на FastAPI

Сервер для загрузки, хранения и анализа аудиозаписей студентов. Поддерживает:
- загрузку ZIP-архива с аудиозаписями и метаданными;
- хранение записей в локальном дереве `records/`;
- пакетный и одиночный анализ через OpenAI;
- сохранение результатов анализа в SQLite и экспорт последних результатов в `analysis.csv`.

Интерактивная документация: http://127.0.0.1:5000/docs
Базовый префикс API: `http://127.0.0.1:5000/api/v1`

---

## Требования

- Python 3.10+ (проверено с 3.11)
- Установленные зависимости из `requirements.txt`

Быстрая установка (Windows, PowerShell):

```pwsh
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Запуск

Из корня репозитория:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

После запуска API будет доступно по адресу `http://127.0.0.1:5000`.

---

## Конфигурация

Настройки определены в файле `app/config.py` и могут быть переопределены через переменные окружения или `.env` в корне проекта (загружается автоматически).

Пример `.env`:

```env
# Корень для хранения загруженных данных
records_dir=records

# URL БД (SQLAlchemy)
database_url=sqlite:///./analysis_results.db

# OpenAI
openai_api_key=sk-...   # ОБЯЗАТЕЛЕН для работы эндпоинтов анализа
openai_model=gpt-audio-mini-2025-12-15

# Для совместимости; в текущей реализации не используется напрямую
ai_analysis_url=https://text-convector-germangch.waw0.amvera.tech/api/v1/send_to_ai_analize
```

Примечания:
- Никогда не коммитьте реальные ключи API в репозиторий.
- `openai_api_key` должен быть задан, иначе анализ будет недоступен.

---

## Структура проекта

```
.
├─ app/
│  ├─ main.py                 # FastAPI-приложение, CORS, подключение роутеров
│  ├─ routes.py               # Эндпоинты: загрузка/список/скачивание/анализ
│  ├─ config.py               # Конфигурация через pydantic-settings
│  └─ DBController/
│     └─ db_router.py         # SQLite-модель и эндпоинты истории
├─ records/                   # Хранилище загруженных сессий (создаётся по требованию)
├─ analysis.csv               # Экспорт последних результатов пакетного анализа
├─ requirements.txt
└─ README.md
```

Фактическая структура для каждой загрузки:

```
records/
  └─ {student_name}/
      └─ {timestamp}/
          ├─ source_audio/      # аудиофайлы (например, 1.mp3, 2.mp3, ...)
          └─ metadata.json      # метаданные, валидируются при загрузке
```

Схема `metadata.json`:

```json
{
  "scena": "<string>",
  "data": ["<text1>", "<text2>", "<text3>", "<text4>"]
}
```

Во время анализа сервер сопоставляет текстовые реплики с аудио по именам файлов: `1.*` — первая реплика, `2.*` — вторая и т. д.

---

## API (префикс: /api/v1)

### Загрузка записей
- Метод/путь: `POST /upload_records`
- Тело: `multipart/form-data`
  - `data`: JSON-строка (как в схеме выше)
  - `file`: ZIP-архив с аудио
- Ответ: `{ filename, files_inside, status }`

### Список студентов и дат
- Метод/путь: `POST /students_hierarhy`
- Ответ: `{ students: string[], students_hierarhy: Record<string, string[]> }`

### Скачать комплект записей
- Метод/путь: `POST /student_records`
- Параметры: `student`, `date`
- Ответ: ZIP-архив папки `records/{student}/{date}`

### Анализ: пакетный (с сохранением в БД)
- Метод/путь: `POST /student_analize_record`
- Параметры: `name`, `date`
- Результат: сохраняет ответы ИИ в SQLite и перезаписывает `analysis.csv`
- Ответ: `{ original: string[], answers: string[] }`

### Анализ: одиночный (без записи в БД)
- Метод/путь: `POST /student_analyze_single`
- Тело: `multipart/form-data`
  - `file`: аудиофайл
  - `language`: напр. `ru`, `en`
  - `transcript`: текст расшифровки
- Ответ: `{ language, transcript, answer }`

### Данные: история студента
- Метод/путь: `GET /get_student_history/{name}`
- Ответ: массив `{ date, original, answer }` (`answer` хранится как JSON-строка в БД)

---

## Примеры запросов (curl)

Загрузка записей:

```bash
curl -X POST "http://127.0.0.1:5000/api/v1/upload_records" \
  -F "data={\"scena\":\"demo\",\"data\":[\"Text 1\",\"Text 2\"]}" \
  -F "file=@records.zip"
```

Список студентов:

```bash
curl -X POST "http://127.0.0.1:5000/api/v1/students_hierarhy"
```

Одиночный анализ:

```bash
curl -X POST "http://127.0.0.1:5000/api/v1/student_analyze_single" \
  -F "file=@1.mp3" \
  -F "language=ru" \
  -F "transcript=Текст расшифровки"
```

Пакетный анализ с сохранением:

```bash
curl -X POST "http://127.0.0.1:5000/api/v1/student_analize_record?name=pomelo&date=2026-03-11_13-17-27"
```

---

## Безопасность и CORS

- CORS в `app/main.py` сейчас открыт для всех источников — для продакшена ограничьте список доменов.
- Храните `openai_api_key` только в переменных окружения/`.env` и не публикуйте его.

---

## Полезные ссылки

- Код приложения: `app/main.py`, `app/routes.py`
- Модели/БД и история: `app/DBController/db_router.py`
- Примерные заметки и расширенная документация: `doc.md`
