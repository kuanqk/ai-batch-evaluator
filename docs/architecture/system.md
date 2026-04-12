# Архитектура: компоненты

```
Browser ──────────────── Django Views (session auth)
                              │
Staff UI ─────────────── /evaluators/… (is_staff)
                              │
External (Beles) ────── DRF /api/… (Token + опц. X-API-Key)
        или            /api/ev/<slug>/… (только X-API-Key конфига)
                              │
                      EvaluationJob / Evaluation (ORM)
                              │
                      Celery process_job / process_file
                              │
             asyncio.run(run_pipeline + EvaluatorConfig?)
                              │
         ┌─────────┼──────────┐
    download    convert    extract → LLM (NITEC)
                   │
              save to ORM; опц. tasks/delivery (Beles/webhook)
```

Проект не использует ApeRAG — собственный pipeline.

## Docker Compose (dev/compose в репозитории)

```
db (postgres) ← app (gunicorn) ← celery (worker)
                      ↑
                    redis
```

- Сервис `app` обычно выполняет миграции перед стартом Gunicorn
- Celery — тот же образ, другая команда

См. также: [auth.md](auth.md), [concurrency.md](concurrency.md), [../operations/deployment.md](../operations/deployment.md).
