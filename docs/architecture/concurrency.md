# Конкурентность: Celery и pipeline

## Celery workers и async

Воркеры Celery — **синхронные** процессы. Async pipeline выполняется внутри задачи через `asyncio.run()`:

```python
@celery_app.task(...)
def process_file(self, eval_id):
    ev = Evaluation.objects.get(pk=eval_id)   # sync ORM
    result = asyncio.run(run_pipeline(...))   # async I/O
    Evaluation.objects.filter(pk=eval_id).update(...)  # sync ORM
```

Семафоры (`config/concurrency.py`) создаются в `init_concurrency()` на каждый `asyncio.run()` — привязаны к текущему event loop.

## Очереди

В `config/settings.py`: маршрутизация на очереди **`evaluation`** и **`maintenance`**. Запуск воркера:

```bash
celery -A config worker --concurrency=5 -Q evaluation,maintenance -l info
```

## Лимиты семафоров

Источник — переменные окружения (см. [../reference/config-env.md](../reference/config-env.md)):

- `NITEC_MAX_WORKERS` — LLM
- `MAX_CONCURRENT_DOWNLOADS` — скачивания
- `MAX_CONCURRENT_VISION` — Vision OCR

Модель **`SystemSettings`** в БД задаёт глобальные лимиты и проверку суммы **`evaluation_slots`** по конфигам; сами семафоры в коде читают **env**, не БД (поведение может быть расширено позже).
