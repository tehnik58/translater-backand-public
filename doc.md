# Training Server (бэкенд)

Небольшой сервер на FastAPI для загрузки, хранения и анализа аудиозаписей студентов. Данные сохраняются в локальном дереве `records/`, поддерживается пакетный и одиночный анализ через внешний AI-сервис, результаты анализа сохраняются в SQLite.

---

## 🔧 Требования

- Python 3.10+ (проверено с 3.11)
- Установите зависимости (см. requirements.txt):
  - fastapi
  - uvicorn[standard]
  - sqlalchemy
  - pydantic>=2
  - pydantic-settings>=2
  - python-multipart
  - requests

Пример установки:

```bash
pip install -r requirements.txt
```

---

## ⚙️ Конфигурация

Настройки определены в [app/config.py](app/config.py) и могут быть переопределены через файл `.env` (загружается из корня проекта). Имена переменных окружения совпадают с названиями полей (в нижнем регистре). См. пример: [.env.example](.env.example)

```env
# Внешний сервис анализа (API root)
ai_analysis_url=https://text-convector-germangch.waw0.amvera.tech

# Модель для внешнего сервиса
ai_model=gpt-4.1-2025-04-14

# Путь к каталогу сессий
records_dir=records

# URL БД (SQLite в формате SQLAlchemy-пути, будет преобразован в файловый путь)
database_url=sqlite:///./analysis_results.db

# Промпты (необязательно)
system_prompt=...
user_prompt=Please analyze the following student transcript and provide feedback and a numeric score.
```

Заметки:
- Для работы анализа необходимо настроить `ai_analysis_url`.
 - Эндпоинты внешнего сервиса, которые использует приложение: `/api/v1/spech_to_text` (распознавание; multipart с `file`) и `/api/v1/ask` (анализ; поля `system_prompt`, `user_prompt`, `model`).

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
- [app/routes/](app/routes/) — пакет с роутерами, разделёнными по логическим группам:
  - [student_hierarchy_routes.py](app/routes/student_hierarchy_routes.py) — эндпоинты для списка и скачивания записей
  - [analysis_routes.py](app/routes/analysis_routes.py) — эндпоинты для анализа записей
  - [upload_routes.py](app/routes/upload_routes.py) — эндпоинты для загрузки записей
- [app/DBController/db_router.py](app/DBController/db_router.py) — модели SQLite и эндпоинты данных
- [records/](records/) — хранилище загруженных данных студентов (создаётся по требованию)
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

Процесс анализа сопоставляет текстовые реплики с аудиофайлами по их числовым именам. При наличии `metadata.json` используется массив `data` и обрабатываются элементы с нечётными индексами (1, 3, 5, ... по 1-базной нумерации), сопоставляя их со следующими чётными файлами (2, 4, 6, ...). Ожидаются аудиофайлы вида `1.mp3`, `2.mp3`, ... Если `metadata.json` отсутствует, файлы обрабатываются по порядку.

---

## 🧩 Эндпоинты API (префикс: `/api/v1`)

Все эндпоинты смонтированы под `/api/v1`.

### Загрузка записей

- Метод/путь: `POST /upload_records`
- Тело: `multipart/form-data`
  - `data`: JSON-строка по схеме выше
  - `file`: архив `.zip` с аудиофайлами внутри (внутренние пути извлекаются в `source_audio/`)
  - `student`: опционально, имя студента; если не задано, берётся из `data.student` или `"unknown"`
- Ответ: `{ filename, files_inside, status, student, date }`

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
- Тело: `multipart/form-data`
  - `name`: имя студента
  - `date`: метка времени сессии (папка в `records/<name>/<date>`)
- Поведение: для каждого файла из `source_audio/` делает распознавание и анализ, сохраняет результат в SQLite; предыдущие результаты для той же пары (name, date) удаляются
- Ответ: `{ student, date, processed: [{ file, transcript, ai_answer_present }] }`

---

### Анализ: одиночный (с сохранением в БД)

- Метод/путь: `POST /student_analyze_single`
- Тело: `multipart/form-data`
  - `file`: аудиофайл (одна реплика)
  - `language`: строка (эхается в ответе как часть параметров, в текущей версии не влияет на логику)
  - `transcript`: опционально, готовая расшифровка; если не задана — выполняется распознавание
  - `student`: опционально, имя студента
- Ответ: `{ student, date, transcript, ai_answer }`

---

### Данные: история студента

- Метод/путь: `GET /get_student_history/{name}`
- Ответ: массив объектов `{ date, original, answer }`. `answer` — сохранённый текст ответа ИИ (массив строк), `original` — исходные тексты (массив строк).

---

## 🗄️ Хранение данных

- URL БД берётся из `database_url` (по умолчанию `sqlite:///./analysis_results.db`), используется `sqlite3`.
- Таблица: `analysis_results(id, student_name, date, original_text, ai_answer)`; поля `original_text` и `ai_answer` содержат JSON-строки с массивами.

---

## 🔐 CORS и безопасность

- CORS сейчас настроен на разрешение всех источников в [app/main.py](app/main.py). В продакшене следует сузить список доменов.
- Настройки сервиса задаются через `.env` или переменные окружения.

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
curl -X POST "http://127.0.0.1:5000/api/v1/student_analize_record" \
  -F "name=pomelo" \
  -F "date=2026-03-11_13-17-27"

```

Примечание: сервер извлекает из ответа внешнего сервиса только текстовую часть. Если ответ приходит как HTML, приложение берёт содержимое блока <pre>... </pre>, чтобы в БД сохранялся чистый текст ответа модели.
```
