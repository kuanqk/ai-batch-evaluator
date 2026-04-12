# AI Batch Evaluator

Система массовой автономной оценки учебных планов педагогов через NITEC LLM.

**Стек:** Django 4.2 · DRF · Celery · Redis · PostgreSQL · Bootstrap 5

## Быстрый старт (Docker)

```bash
cp .env.example .env
# Установить NITEC_API_KEY и DJANGO_SECRET_KEY в .env

docker compose up -d --build
# После запуска:
docker compose exec app python manage.py createsuperuser
open http://localhost:8502
```

## Локально (без Docker)

```bash
cp .env.example .env
# Запустить PostgreSQL и Redis; настроить DATABASE_URL, REDIS_URL

make install
make migrate
make createsuperuser
make run

# В отдельном терминале:
make celery-worker
```

## Тесты

```bash
python -m pytest tests/ -v
```

## Структура

```
apps/accounts/    — авторизация (CustomUser)
apps/batch/       — EvaluationJob, Evaluation, UI батча, DRF /api/
apps/evaluators/  — EvaluatorConfig, рубрики, промпты, staff UI
apps/single/      — оценка одного документа (браузер)
pipeline/         — async: скачивание, конвертация, извлечение текста, LLM
tasks/            — Celery (evaluate, maintenance, delivery)
templates/        — Bootstrap 5
docs/             — см. docs/README.md (индекс)
```

## API

Глобальные JSON-эндпоинты: префикс **`/api/`** (батч, оценки, stats, health).  
Аутентификация: **Token** или сессия; при заданном **`EVALUATOR_API_KEY`** — также заголовок **`X-API-Key`**.

Per-config (мультиконфиг): **`/api/ev/<slug>/evaluate/`**, **`batch`**, **`health`**, **`stats`** — ключ из **`EvaluatorConfig.api_key`**.

Документация: **`docs/README.md`** (индекс), **`docs/reference/api.md`**, **`docs/getting-started/overview.md`**, **`docs/sprints/README.md`**.
