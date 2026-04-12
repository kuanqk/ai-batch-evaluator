# Устранение неполадок

## Логи

```bash
# systemd
journalctl -u orleu-batch-evaluator -f
journalctl -u orleu-batch-celery -f
```

## Celery

```bash
celery -A config inspect active
celery -A config inspect reserved
celery -A config purge   # осторожно: очистить очередь
```

Убедитесь, что воркер запущен с очередями **`evaluation,maintenance`**.

## База и Redis

- `GET /api/health/` — проверка PostgreSQL и Redis
- Per-config: `GET /api/ev/<slug>/health/`

## Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| 401/403 на API | Token, `EVALUATOR_API_KEY`, per-config `X-API-Key` |
| Задачи не выполняются | Redis, запущен ли worker, правильные `-Q` |
| 429 от NITEC | Уменьшить `NITEC_MAX_WORKERS`, смотреть rate limit |
| Пустой текст из PDF | Vision OCR, лимиты `MAX_CONCURRENT_VISION`, токены |

Конфигурация: [../reference/config-env.md](../reference/config-env.md).  
Деплой: [deployment.md](deployment.md).
