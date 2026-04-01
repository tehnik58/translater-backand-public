# Training Server — бэкенд на FastAPI

Сервер для загрузки, хранения и анализа аудиозаписей студентов. Поддерживает:
- загрузку ZIP-архива с аудиозаписями и метаданными;
- хранение записей в локальном дереве `records/`;
- пакетный и одиночный анализ через внешний AI-сервис;
- сохранение результатов анализа в SQLite.

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

# URL БД (SQLite в формате SQLAlchemy-пути, будет преобразован в файловый путь)
database_url=sqlite:///./analysis_results.db

# Модель для внешнего сервиса
ai_model=gpt-4.1-2025-04-14

# Внешний сервис анализа (API root)
ai_analysis_url=https://text-convector-germangch.waw0.amvera.tech

# Промпты (необязательно, есть значения по умолчанию)
system_prompt=... 
user_prompt=Please analyze the following student transcript and provide feedback and a numeric score.
```

Примечания:
- Никогда не коммитьте реальные ключи API в репозиторий.

---

## Структура проекта

```
.
├─ app/
│  ├─ main.py                 # FastAPI-приложение, CORS, подключение роутеров
│  ├─ config.py               # Конфигурация через pydantic-settings
│  ├─ ai_client.py            # Клиент внешнего сервиса (STT и анализ)
│  ├─ routes/                 # Эндпоинты: загрузка/список/скачивание/анализ
│  │  ├─ upload_routes.py
│  │  ├─ student_hierarchy_routes.py
│  │  └─ analysis_routes.py
│  └─ DBController/
│     └─ db_router.py         # Работа с SQLite (sqlite3)
├─ records/                   # Хранилище загруженных сессий (создаётся по требованию)
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
  - `student`: опционально, имя студента; если не задано, берётся из `data.student` или `"unknown"`
- Ответ: `{ filename, files_inside, status, student, date }`

### Список студентов и дат
- Метод/путь: `POST /students_hierarhy`
- Ответ: `{ students: string[], students_hierarhy: Record<string, string[]> }`

### Скачать комплект записей
- Метод/путь: `POST /student_records`
- Параметры: `student`, `date`
- Ответ: ZIP-архив папки `records/{student}/{date}`

### Анализ: пакетный (с сохранением в БД)
- Метод/путь: `POST /student_analize_record`
- Тело: `multipart/form-data`
  - `name`: имя студента
  - `date`: метка времени сессии (папка в `records/<name>/<date>`)
- Поведение: для каждого файла из `source_audio/` делает распознавание и анализ, сохраняет результат в SQLite; предыдущие результаты для той же пары (name, date) удаляются
- Ответ: `{ student, date, processed: [{ file, transcript, ai_answer_present }] }`

### Анализ: одиночный (с сохранением в БД)
- Метод/путь: `POST /student_analyze_single`
- Тело: `multipart/form-data`
  - `file`: аудиофайл (одна реплика)
  - `language`: строка (эхается в ответе как часть параметров, в текущей версии не влияет на логику)
  - `transcript`: опционально, готовая расшифровка; если не задана — выполняется распознавание
  - `student`: опционально, имя студента
- Ответ: `{ student, date, transcript, ai_answer }`

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
curl -X POST "http://127.0.0.1:5000/api/v1/student_analize_record" \
  -F "name=pomelo" \
  -F "date=2026-03-11_13-17-27"
```

---

## Безопасность и CORS

- CORS в `app/main.py` сейчас открыт для всех источников — для продакшена ограничьте список доменов.
- Настройки модели и сервиса задаются через `.env`.

---

## Полезные ссылки

- Код приложения: [app/main.py](app/main.py), [app/routes/](app/routes/)
- Работа с БД и история: [app/DBController/db_router.py](app/DBController/db_router.py)
- Расширенная документация: [doc.md](doc.md)
- Пример переменных окружения: [.env.example](.env.example)
