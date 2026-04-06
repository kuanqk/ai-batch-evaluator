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
apps/accounts/   — авторизация (CustomUser)
apps/batch/      — основной модуль (EvaluationJob, Evaluation, UI, DRF API)
apps/single/     — оценка одного документа
pipeline/        — async логика (скачивание, конвертация, LLM)
tasks/           — Celery tasks
templates/       — Bootstrap 5 UI
docs/            — документация и спринты
```

## API (DRF, TokenAuthentication)

```
POST /api/batch/upload/         — загрузить CSV/Excel
GET  /api/batch/<id>/           — прогресс задания
POST /api/evaluate/             — один документ (для Beles)
GET  /api/evaluations/          — список оценок
GET  /api/stats/                — статистика
GET  /api/health/               — статус сервиса
```

Подробнее: `docs/sprints/README.md`
