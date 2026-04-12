# Бэкап и миграции

## Перед `migrate` в проде

1. Сделать дамп БД:

```bash
pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d_%H%M%S).sql
```

Или для контейнера PostgreSQL — см. [deployment.md](deployment.md).

2. Убедиться, что откат возможен (копия файла, тест на staging).

3. Выполнить:

```bash
python manage.py migrate
```

## Восстановление

```bash
psql "$DATABASE_URL" < backup_YYYYMMDD.sql
```

## Перенос `evaluator_db` (отдельный сценарий)

Пошагово описано в [deployment.md](deployment.md) (фаза 2): остановка сервиса, дамп, восстановление в `batch-postgres`, смена `DATABASE_URL`.

## Чеклист продакшена (кратко)

- `DEBUG=false`, уникальный `DJANGO_SECRET_KEY`
- `ALLOWED_HOSTS` без `*` в проде
- TLS на Nginx
- Секреты только в `.env` / vault

Полный список — раздел «Продакшен» в [deployment.md](deployment.md).
