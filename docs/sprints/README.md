# Спринты

| # | Название | Статус |
|---|----------|--------|
| [01](sprint-01.md) | Django scaffold, ORM, auth, API, templates | ✅ Завершён |
| [02](sprint-02.md) | Pipeline (downloader, converter, extractor, llm) | ✅ Завершён (перенесён из FastAPI) |
| [03](sprint-03.md) | Celery + batch API (интеграция Django ORM) | ✅ Завершён |
| [04](sprint-04.md) | UI templates + results + Excel export | ✅ Завершён |
| [05](sprint-05.md) | apps/single (миграция evaluator-main без ApeRAG) + tests | 🔜 Следующий |

## Текущее состояние

После Sprint 1 (`main` branch) полностью работает:
- Django + Gunicorn сервер
- PostgreSQL + Django ORM (модели + миграции)
- Celery + Redis
- DRF API (Token auth)
- Browser UI (session auth, Bootstrap 5)
- Pipeline (async, без изменений)
- Docker Compose (one-command deploy)

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
