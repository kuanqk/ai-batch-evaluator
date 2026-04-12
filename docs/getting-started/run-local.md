# Запуск локально

## Без Docker

Нужны запущенные PostgreSQL и Redis, настроенные в `.env` (`DATABASE_URL`, `REDIS_URL`).

```bash
source .venv/bin/activate
make run
```

Во втором терминале — worker Celery (очереди как в `config/settings.py`):

```bash
make celery-worker
# эквивалентно:
# celery -A config worker --concurrency=5 -Q evaluation,maintenance -l info
```

Приложение: `http://localhost:8502` (порт задаётся командой `runserver` / Gunicorn).

## Docker Compose

```bash
cp .env.example .env
# заполнить секреты

docker compose up -d --build
docker compose exec app python manage.py createsuperuser
```

Логи приложения: `make docker-logs` или `docker compose logs -f app`.

## Полезно

- Проверка конфигурации: `python manage.py check`
- Статика для прода: `make collectstatic`
- Beat (если используется): `make celery-beat`

Продакшен: [../operations/deployment.md](../operations/deployment.md).
