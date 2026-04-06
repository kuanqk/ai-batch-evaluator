# Sprint 1 — Django Scaffold ✅

**Статус:** ЗАВЕРШЁН

## Что сделано

### Django проект
- `manage.py` — точка входа
- `config/settings.py` — Django settings (DB из DATABASE_URL, NITEC vars, Celery, DRF, Logging)
- `config/urls.py` — root URLs
- `config/wsgi.py`, `config/asgi.py`
- `config/celery.py` — Celery app с Django setup (`app.config_from_object`)
- `config/__init__.py` — инициализирует Celery при запуске Django

### Авторизация
- `apps/accounts/` — `CustomUser(AbstractUser)`, login/logout views, admin
- Session auth для браузера (`@login_required`)
- DRF TokenAuthentication для API (`X-API-Key` header)
- `LOGIN_URL`, `LOGIN_REDIRECT_URL` настроены

### Модели ORM
- `apps/batch/models.py`:
  - `EvaluationJob` — задание, атомарные счётчики processed/failed
  - `Evaluation` — одна запись, все 25 баллов, LLM результат
- Индексы: status, created_at, job+status, score_level, city, trainer
- Миграции: `apps/accounts/migrations/0001_initial.py`, `apps/batch/migrations/0001_initial.py`

### DRF API (`/api/`)
- `apps/batch/api.py` + `apps/batch/api_urls.py`
- POST `/api/batch/upload/` — загрузка CSV/Excel
- GET `/api/batch/<id>/` — прогресс задания
- POST `/api/batch/<id>/retry-failed/`, `/pause/`, `/resume/`
- GET `/api/evaluations/` — список с фильтрами
- GET/POST `/api/evaluations/<id>/`, `/retry/`
- POST `/api/evaluate/` — single evaluation (для Beles)
- GET `/api/stats/`, `/api/health/`

### Browser UI
- `apps/batch/views.py` — dashboard, upload, results, export
- `apps/batch/urls.py`
- Templates (Bootstrap 5):
  - `templates/base.html` — с боковым меню и navbar
  - `templates/accounts/login.html`
  - `templates/batch/dashboard.html` — список заданий с прогресс-баром
  - `templates/batch/upload.html` — форма загрузки CSV/Excel
  - `templates/batch/results.html` — таблица с фильтрами, пагинацией, Excel export

### Pipeline (перенесён без изменений)
- `pipeline/` — все файлы сохранены
- Обновлены импорты: `from django.conf import settings` + uppercase vars (NITEC_API_KEY, etc.)
- `config/concurrency.py` — lazy init семафоров (вызывается в начале каждого asyncio.run())

### Celery tasks (рефакторинг под Django ORM)
- `tasks/evaluate.py` — полностью переписан:
  - ORM read/write — **sync** (до и после asyncio.run)
  - `asyncio.run(run_pipeline(...))` — только async I/O
  - Атомарное клеймирование через `Evaluation.objects.filter(status='pending').update(...)`
  - `_try_finalize_job` — `select_for_update()` + update
- `tasks/maintenance.py` — cleanup_tmp через Django settings
- `monitoring/tracker.py` — sync Django ORM (убрана asyncpg зависимость)

### Infrastructure
- `requirements.txt` — Django, DRF, psycopg2-binary, celery, gunicorn
- `Dockerfile` — CMD gunicorn
- `docker-compose.yml` — migrate + collectstatic перед gunicorn, healthcheck redis
- `.env.example` — все переменные

### Удалены старые файлы
- `main.py` (FastAPI)
- `db/connection.py`, `db/models.py`, `db/queries.py` (asyncpg)
- `api/batch.py`, `api/evaluation.py`, `api/deps.py`, `api/batch_upload.py` (FastAPI)
- `config/settings.py` (pydantic-settings) → заменён Django settings

## Проверка

```bash
python manage.py check   # 0 issues
python manage.py makemigrations  # migrations created
```
