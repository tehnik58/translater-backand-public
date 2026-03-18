# Training Server (бэкенд)

Небольшой сервер на FastAPI для загрузки, хранения и анализа аудиозаписей студентов. Данные сохраняются в локальном дереве `records/`, поддерживается пакетный и одиночный анализ через OpenAI, результаты анализа сохраняются в SQLite.

---

## 🔧 Требования

- Python 3.10+ (проверено с 3.11)
- Установите зависимости (минимальный набор):
  - fastapi
  - uvicorn[standard]
  - sqlalchemy
  - pydantic>=2
  - pydantic-settings>=2
  - python-multipart
  - openai>=1.0

Пример установки:

```bash
pip install fastapi "uvicorn[standard]" sqlalchemy "pydantic>=2" "pydantic-settings>=2" python-multipart "openai>=1.0"
```

---

## ⚙️ Конфигурация

Настройки определены в [app/config.py](app/config.py) и могут быть переопределены через файл `.env` (загружается из корня проекта). Имена переменных окружения совпадают с названиями полей (в нижнем регистре):

```env
# Унаследовано, сейчас напрямую эндпоинтами не используется
ai_analysis_url=https://text-convector-germangch.waw0.amvera.tech/api/v1/send_to_ai_analize

# Корень хранения загрузок
records_dir=records

# URL базы данных SQLAlchemy (относительно текущей рабочей директории)
database_url=sqlite:///./analysis_results.db

# OpenAI
openai_api_key=sk-...             # ОБЯЗАТЕЛЕН для работы эндпоинтов анализа
openai_model=gpt-audio-mini-2025-12-15
```

Заметки:
- Для работы анализа необходимо задать `openai_api_key`. Клиент инициализируется из этого ключа при старте.
- `ai_analysis_url` сохранён для совместимости, но в текущем потоке на основе OpenAI не используется.

---

## 🚀 Запуск

Из корня репозитория:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

Базовый URL: http://127.0.0.1:5000/api/v1

Интерактивная документация: http://127.0.0.1:5000/docs

---

## 📁 Структура проекта

- [app/main.py](app/main.py) — приложение FastAPI, CORS, подключение роутеров
- [app/routes.py](app/routes.py) — эндпоинты для загрузки, списка, скачивания и AI-анализа
- [app/DBController/db_router.py](app/DBController/db_router.py) — модели SQLite и эндпоинты данных
- [records/](records/) — хранилище загруженных данных студентов (создаётся по требованию)
- [analysis.csv](analysis.csv) — последний экспорт результатов пакетного анализа (перезаписывается)
- Файл SQLite по `database_url` (по умолчанию `analysis_results.db` в текущей рабочей директории)

---

## 🧠 Формат данных

Каждая загрузка создаёт папку в `records/`:

```
records/
  └─ {student_name}/
      └─ {timestamp}/
          ├─ source_audio/      # извлечённые аудиофайлы (например, 1.mp3, 2.mp3, ...)
          └─ metadata.json      # переданные пользователем метаданные
```

Схема `metadata.json` (валидируется кодом):

```json
{
  "scena": "<string>",
  "data": ["<text1>", "<text2>", "<text3>", "<text4>", "..."]
}
```

Процесс анализа сопоставляет текстовые реплики с аудиофайлами по их числовым именам: `1.*` соотносится с первой текстовой записью и т. д. (ожидаются имена вида `1.mp3`, `2.mp3`, ...).

---

## 🧩 Эндпоинты API (префикс: `/api/v1`)

Все эндпоинты смонтированы под `/api/v1`.

### Загрузка записей

- Метод/путь: `POST /upload_records`
- Тело: `multipart/form-data`
  - `data`: JSON-строка по схеме выше
  - `file`: архив `.zip` с аудиофайлами внутри (внутренние пути извлекаются в `source_audio/`)
- Ответ: `{ filename, files_inside, status }`

---

### Список студентов и дат

- Метод/путь: `POST /students_hierarhy`
- Ответ: `{ students: string[], students_hierarhy: Record<string, string[]> }`

---

### Скачать комплект записей

- Метод/путь: `POST /student_records`
- Параметры запроса: `student`, `date`
- Ответ: ZIP-архив (двоичный) папки `records/{student}/{date}`

---

### Анализ: пакетный (с сохранением в БД)

- Метод/путь: `POST /student_analize_record`
- Параметры запроса: `name`, `date`
- Поведение: Для каждой пары «текст + аудио» выполняется вызов OpenAI и результат сохраняется в SQLite. Также формируется CSV-снимок в [analysis.csv](analysis.csv).
- Ответ: `{ original: string[], answers: string[] }`

---

### Анализ: одиночный (без записи в БД)

- Метод/путь: `POST /student_analyze_single`
- Тело: `multipart/form-data`
  - `file`: аудиофайл (одна реплика)
  - `language`: например, `ru`, `en` (возвращается в ответе)
  - `transcript`: текст расшифровки аудио
- Ответ: `{ language, transcript, answer }`

---

### Данные: история студента

- Метод/путь: `GET /get_student_history/{name}`
- Ответ: массив объектов `{ date, original, answer }`. `answer` — сохранённый результат ИИ.

---

## 🗄️ Хранение данных

- URL БД берётся из `database_url` (по умолчанию `sqlite:///./analysis_results.db`).
- Модель SQLAlchemy: `analysis_results(id, student_name, date, original_text, ai_answer)`.
- Файл-экспорт: [analysis.csv](analysis.csv) перезаписывается при пакетном анализе.

---

## 🔐 CORS и безопасность

- CORS сейчас настроен на разрешение всех источников в [app/main.py](app/main.py). В продакшене следует сузить список доменов.
- Устанавливайте `openai_api_key` через `.env` или переменные окружения. Не храните секреты в коде при прод-использовании.

---

## 🧪 Быстрые примеры (curl)

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
