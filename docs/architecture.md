# Архитектура

## Компоненты

```
Browser ──────────────── Django Views (session auth)
                              │
External (Beles) ────── DRF API (X-API-Key / Token)
                              │
                      EvaluationJob / Evaluation (ORM)
                              │
                      Celery process_job.delay()
                              │
                   ┌──────────┴──────────┐
            process_file(1)       process_file(N)
                   │
             asyncio.run(run_pipeline)
                   │
         ┌─────────┼──────────┐
    download    convert    extract
                   │
             evaluate_with_llm  ←── NITEC API
                   │
              save to ORM (Django)
```

## Авторизация

```
Browser:   POST /accounts/login/ → session cookie → @login_required
API:       Header X-API-Key      → DRF TokenAuthentication
Admin:     /admin/               → is_staff required
```

## Celery + async pipeline

Celery workers — **синхронные** процессы. Async pipeline запускается через `asyncio.run()`:

```python
@celery_app.task(...)
def process_file(self, eval_id):
    ev = Evaluation.objects.get(pk=eval_id)   # sync ORM
    result = asyncio.run(run_pipeline(...))    # async I/O
    Evaluation.objects.filter(pk=eval_id).update(**result)  # sync ORM
```

Семафоры (concurrency limits) создаются внутри каждого `asyncio.run()` — они живут в рамках одного event loop.

## Docker Compose

```
db (postgres) ← app (gunicorn) ← celery (worker)
                      ↑
                    redis
```

- `app` запускает `python manage.py migrate` перед стартом gunicorn
- `celery` использует тот же образ, другую команду
