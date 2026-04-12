# Спринты

| # | Название | Статус |
|---|----------|--------|
| [01](sprint-01.md) | Django scaffold, ORM, auth, API, templates | ✅ Завершён |
| [02](sprint-02.md) | Pipeline (downloader, converter, extractor, llm) | ✅ Завершён (перенесён из FastAPI) |
| [03](sprint-03.md) | Celery + batch API (интеграция Django ORM) | ✅ Завершён |
| [04](sprint-04.md) | UI templates + results + Excel export | ✅ Завершён |
| [05](sprint-05.md) | apps/single + pytest-база | ✅ Завершён |

## Текущее состояние (main)

- Django + Gunicorn / `runserver`
- PostgreSQL + ORM, миграции (`accounts`, `batch`, `evaluators`)
- Celery + Redis; очереди **`evaluation`**, **`maintenance`** (см. `CELERY_TASK_ROUTES`)
- DRF: Token/сессия; опционально **`EVALUATOR_API_KEY`** + заголовок `X-API-Key`
- **`apps/evaluators`**: мультиконфиг, staff UI, per-config API **`/api/ev/<slug>/…`**
- Pipeline async в Celery (`asyncio.run(run_pipeline)`), доставка результатов — `tasks/delivery.py`
- Docker Compose — см. корневой `docker-compose.yml`
- Документация: индекс `docs/README.md`, справочник `docs/reference/`, деплой `docs/operations/deployment.md`

## Запуск (dev)

```bash
cp .env.example .env  # настроить переменные
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8502

# В другом терминале:
celery -A config worker --concurrency=5 -Q evaluation,maintenance -l info
```

## Запуск (Docker)

```bash
docker compose up -d --build
docker compose exec app python manage.py createsuperuser
```
