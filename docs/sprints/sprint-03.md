# Sprint 3 — Celery + Batch API

**Статус:** done

## Цель

Загрузка CSV/Excel → создание `evaluation_jobs` + строк `evaluations` → фоновая обработка → прогресс по job.

## Задачи

- [x] `db/queries.py` — insert/update job, insert evaluations, атомарные `processed`/`failed`, выборки по job
- [x] `monitoring/tracker.py` — fire-and-forget обёртки над queries
- [x] `tasks/evaluate.py` — `process_job(job_id)`, `process_file(eval_id)` с вызовом pipeline из Sprint 2
- [x] `api/batch.py` — `POST /batch/upload`, `GET /batch/{job_id}`
- [x] `api/evaluation.py` — `POST /evaluate` (одиночная оценка)
- [x] Опционально: `POST /batch/{id}/retry-failed`, pause/resume
- [x] `main.py` — подключить роутеры, `X-API-Key` где нужно

## Проверка

CSV с 5–10 строками → job в `running` → строки переходят в `done`/`failed`, счётчики job корректны.

```bash
# API + worker + Redis + Postgres
docker compose up -d --build
# worker в отдельном терминале или сервис celery уже в compose

curl -s -H "X-API-Key: $EVALUATOR_API_KEY" \
  -F "file=@sample.csv" -F "name=test" \
  http://localhost:8502/batch/upload

curl -s http://localhost:8502/batch/1
```

## Done (2026-04-05)

- **`db/queries.py`:** создание job, bulk insert evaluations, `claim_evaluation`, сохранение успеха/ошибки, `increment_job_*`, `try_finalize_job`, `job_batch_stats`, webhook payload; миграции в `db/models.py`: `job_id` nullable, `material_id`, `paused`.
- **`monitoring/tracker.py`:** `track_step` + `track_step_async` (best-effort).
- **`tasks/evaluate.py`:** `process_job` расставляет `process_file`; `process_file` вызывает `run_pipeline`, пишет `reports/{eval_id}.json`, webhook при завершении job; `JobPaused` → retry Celery.
- **`api/batch_upload.py`:** парсинг CSV / `.xlsx` с колонками `file_path`, `file_url`.
- **`api/deps.py`:** `X-API-Key` если задан `EVALUATOR_API_KEY` в `.env`.
- **`main.py`:** роутеры `/batch/*`, `/evaluate`.

## Следующий шаг

→ [sprint-04.md](sprint-04.md)
