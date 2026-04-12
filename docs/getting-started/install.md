# Установка

## Требования

- Python 3.11+ (см. окружение проекта)
- PostgreSQL и Redis (или Docker Compose из корня репозитория)

## Виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Либо: `make install` (создаёт `.venv` и ставит зависимости).

## Переменные окружения

```bash
cp .env.example .env
```

Обязательно задайте минимум:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `NITEC_API_KEY`

Полная таблица переменных: [../reference/config-env.md](../reference/config-env.md).

## Миграции и суперпользователь

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Тесты

```bash
python -m pytest tests/ -v
```
