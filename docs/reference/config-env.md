# Конфигурация (.env)

Файл `.env` в корне проекта. Шаблон: **`.env.example`**.  
Переменные читаются в **`config/settings.py`** через `os.environ` (без pydantic в рантайме).

---

## Пример

```env
DJANGO_SECRET_KEY=change-me-long-random
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://orleu:password@localhost:5432/orleu_batch_evaluator
REDIS_URL=redis://localhost:6379/1

NITEC_API_KEY=sk-xxx
NITEC_BASE_URL=https://llm.nitec.kz/v1
NITEC_MODEL=openai/gpt-oss-120b
NITEC_VISION_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
NITEC_MAX_TOKENS=4096

MIN_TEXT_CHARS=50
VISION_MAX_PAGES=10
VISION_DPI=150

NITEC_MAX_WORKERS=5
MAX_CONCURRENT_DOWNLOADS=20
MAX_CONCURRENT_VISION=3

EVALUATOR_API_KEY=

TMP_DIR=/tmp/orleu
REPORTS_DIR=reports
RUBRICS_DIR=rubrics

LOG_LEVEL=INFO
```

Порт HTTP приложения задаётся командой запуска (**Gunicorn** / `runserver`), не отдельной переменной `PORT` в `settings.py`.

---

## Описание переменных

### Django и БД

| Переменная | Описание |
|------------|----------|
| `DJANGO_SECRET_KEY` | Секрет Django. **Обязателен в проде.** |
| `DEBUG` | `true` / `false` |
| `ALLOWED_HOSTS` | Список через запятую |
| `DATABASE_URL` | PostgreSQL DSN (**обязательно**) |
| `REDIS_URL` | Celery broker и result backend |

### NITEC LLM

| Переменная | По умолчанию (в коде) | Описание |
|------------|------------------------|----------|
| `NITEC_API_KEY` | — | Bearer для API |
| `NITEC_BASE_URL` | `https://llm.nitec.kz/v1` | OpenAI-совместимый endpoint |
| `NITEC_MODEL` | `openai/gpt-oss-120b` | Основная модель оценки |
| `NITEC_VISION_MODEL` | Qwen3-VL | Vision OCR (только base64-изображения) |
| `NITEC_MAX_TOKENS` | `4096` | Лимит ответа |

`NITEC_MODEL` подхватывается при работе pipeline из настроек; для режима **без** `EvaluatorConfig` используются эти значения.

### Извлечение текста и Vision

| Переменная | По умолчанию |
|------------|----------------|
| `MIN_TEXT_CHARS` | `50` |
| `VISION_MAX_PAGES` | `10` |
| `VISION_DPI` | `150` |

При наличии **`EvaluatorConfig`** соответствующие поля в БД переопределяют дефолты для этой оценки.

### Конкурентность (процесс)

Семафоры в **`config/concurrency.py`** инициализируются из:

| Переменная | Описание |
|------------|----------|
| `NITEC_MAX_WORKERS` | Параллельные запросы к LLM внутри одного event loop |
| `MAX_CONCURRENT_DOWNLOADS` | Параллельные скачивания |
| `MAX_CONCURRENT_VISION` | Параллельные Vision OCR |

> Модель **`SystemSettings`** в админке задаёт глобальные лимиты «на бумаге» и проверку суммы **`evaluation_slots`**; сами семафоры пока читают **только** переменные окружения выше, не БД.

### API

| Переменная | Описание |
|------------|----------|
| `EVALUATOR_API_KEY` | Если непустой — глобальные защищённые DRF-эндпоинты требуют заголовок `X-API-Key` с этим значением (дополнительно к Token/сессии). |

### Пути

| Переменная | Описание |
|------------|----------|
| `TMP_DIR` | Временные файлы |
| `REPORTS_DIR` | JSON-отчёты по `eval_id` |
| `RUBRICS_DIR` | Файловые рубрики по умолчанию (в мультиконфиге возможны загрузки в БД) |

---

## NITEC: какие модели к чему

| Модель | Назначение |
|--------|------------|
| `openai/gpt-oss-120b` | Основная оценка |
| `Qwen/Qwen3-VL-235B-A22B-Instruct` | Vision OCR (страницы PDF → PNG → API) |
| `deepseek-ai/DeepSeek-OCR` | **Не использовать** для текста (возвращает bbox, не смысл) |

Аудио/Whisper в модели `EvaluatorConfig` заложены **на будущее**, отдельного пайплайна в коде пока нет.

---

## Полезные команды

```bash
source .venv/bin/activate   # или venv проекта

# Celery (очереди должны совпадать с CELERY_TASK_ROUTES в settings)
celery -A config inspect active
celery -A config purge

# Django
python manage.py check
python manage.py migrate
```

Сервисы systemd и прод-порты см. **`docs/operations/deployment.md`** и каталог **`deploy/`**.
