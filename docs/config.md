# Конфигурация (.env)

Файл `.env` в корне проекта. Шаблон: `.env.example`.
Управляется через `config/settings.py` (pydantic-settings — авто-валидация при старте).

---

## Полный `.env.example`

```env
# ─── PostgreSQL ──────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://orleu:password@localhost:5432/orleu_batch_evaluator

# ─── Redis ───────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/1

# ─── NITEC LLM ───────────────────────────────────────────────────────────────
NITEC_API_KEY=sk-xxx
NITEC_BASE_URL=https://llm.nitec.kz/v1
NITEC_MODEL=openai/gpt-oss-120b
NITEC_VISION_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
NITEC_MAX_TOKENS=4096

# ─── Аутентификация ──────────────────────────────────────────────────────────
EVALUATOR_API_KEY=your-secret-key-here   # X-API-Key для входящих запросов

# ─── Конкурентность ──────────────────────────────────────────────────────────
NITEC_MAX_WORKERS=5        # параллельных запросов к LLM (семафор)
MAX_CONCURRENT_DOWNLOADS=20  # параллельных скачиваний
MAX_CONCURRENT_VISION=3    # параллельных Vision OCR (дорого по токенам)
CELERY_WORKERS=5           # количество Celery воркеров

# ─── Пути ────────────────────────────────────────────────────────────────────
TMP_DIR=/tmp/orleu                              # временные файлы (авто-очистка)
REPORTS_DIR=/opt/orleu-batch-evaluator/reports  # JSON отчёты (постоянно)
RUBRICS_DIR=/opt/orleu-batch-evaluator/rubrics  # рубрики (не менять)

# ─── Приложение ──────────────────────────────────────────────────────────────
DEBUG=False
LOG_LEVEL=INFO
PORT=8502
```

---

## Описание переменных

### База данных

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | — | PostgreSQL DSN. **Обязательно.** |
| `REDIS_URL` | `redis://localhost:6379/1` | Redis для Celery broker + backend |

### NITEC LLM

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `NITEC_API_KEY` | — | Bearer token. **Обязательно.** |
| `NITEC_BASE_URL` | `https://llm.nitec.kz/v1` | Базовый URL API |
| `NITEC_MODEL` | `openai/gpt-oss-120b` | Модель для оценки. Менять без перезапуска |
| `NITEC_VISION_MODEL` | `Qwen/Qwen3-VL-235B-A22B-Instruct` | Vision OCR для сканированных документов |
| `NITEC_MAX_TOKENS` | `4096` | `max_tokens` для запроса оценки |

> **Важно:** `NITEC_MODEL` читается при каждом запросе — можно менять в `.env` без рестарта.

### Аутентификация

| Переменная | Описание |
|------------|----------|
| `EVALUATOR_API_KEY` | Ключ для всех защищённых эндпоинтов (`X-API-Key` header). **Обязательно.** |

### Конкурентность

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `NITEC_MAX_WORKERS` | `5` | Семафор параллельных LLM запросов. Начать с 5, уменьшить при 429 |
| `MAX_CONCURRENT_DOWNLOADS` | `20` | Параллельных скачиваний файлов |
| `MAX_CONCURRENT_VISION` | `3` | Параллельных Vision OCR запросов |
| `CELERY_WORKERS` | `5` | Количество Celery процессов. Перезапуск celery при изменении |

> **Настройка под rate limit NITEC:** если появляются 429 ошибки → уменьшить `NITEC_MAX_WORKERS` до 3.

### Пути

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `TMP_DIR` | `/tmp/orleu` | Временные файлы. Celery beat очищает старше 1 часа |
| `REPORTS_DIR` | `reports` | JSON отчёты каждой оценки. Создаётся при старте |
| `RUBRICS_DIR` | `rubrics` | Папка с рубриками (не изменять) |

### Приложение

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DEBUG` | `False` | В DEBUG режиме: hot-reload, более детальные ошибки |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `PORT` | `8502` | Порт uvicorn |

---

## NITEC модели (справка)

| Модель | Использование | Статус |
|--------|--------------|--------|
| `openai/gpt-oss-120b` | **Основная оценка** | ✅ Быстрая |
| `Qwen/Qwen3-VL-235B-A22B-Instruct` | **Vision OCR** (только base64!) | ✅ |
| `deepseek-ai/DeepSeek-V3.2` | Альтернатива основной | ✅ Медленнее |
| `moonshotai/Kimi-K2.5` | Резерв #1 | ✅ |
| `openai/whisper-large-v3-turbo` | Аудио → текст (будущее) | ✅ |
| `BAAI/bge-m3` | Embedding (будущее) | ✅ |
| `deepseek-ai/DeepSeek-OCR` | ❌ Только bbox, не текст | Не использовать |

Подробнее: `orleu-evaluator-main/nitec-models-recommendation.md`

---

## Управление сервисами

```bash
# Статус
systemctl status orleu-batch-evaluator
systemctl status orleu-batch-celery
systemctl status orleu-batch-beat

# Рестарт
systemctl restart orleu-batch-evaluator
systemctl restart orleu-batch-celery   # нужен при изменении CELERY_WORKERS

# Логи
journalctl -u orleu-batch-celery -f
tail -f /var/log/orleu-batch-evaluator/app.log

# Сменить LLM модель (без рестарта)
nano /opt/orleu-batch-evaluator/.env   # изменить NITEC_MODEL
# Перезапуск НЕ нужен — читается при каждом запросе

# Изменить количество воркеров
nano /opt/orleu-batch-evaluator/.env   # изменить CELERY_WORKERS
systemctl restart orleu-batch-celery   # нужен рестарт
```

---

## Полезные команды

```bash
source .venv/bin/activate

# Проверить очередь Celery
celery -A config.celery inspect active
celery -A config.celery inspect reserved

# Принудительно завершить все задачи
celery -A config.celery purge

# Проверить Job вручную
python -c "
import asyncio
from db.connection import init_db
from db.queries import get_dashboard_stats
async def main():
    await init_db()
    print(await get_dashboard_stats())
asyncio.run(main())
"

# Запуск миграций (идемпотентно)
python -c "
import asyncio
from db.connection import init_db, close_db
from db.models import create_tables
async def main():
    await init_db()
    await create_tables()
    await close_db()
asyncio.run(main())
"
```
