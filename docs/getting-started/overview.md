# Обзор

Система массовой автономной оценки учебных планов педагогов с помощью NITEC LLM.

## Цель

Принять CSV/Excel с URL файлов → скачать → извлечь текст → оценить по рубрике (LLM) → сохранить 25 оценок (s1_c1…s5_c5) → выдать результат через UI или API.

## Стек

| Слой | Технология |
|------|------------|
| Web | Django 4.2 + Gunicorn |
| API | Django REST Framework |
| БД | PostgreSQL + Django ORM |
| Очереди | Celery 5 + Redis |
| Pipeline | Python async (`asyncio.run` внутри Celery) |
| LLM | NITEC (`openai/gpt-oss-120b` и др.) |
| Vision OCR | Qwen3-VL (PNG base64) |
| UI | Django templates + Bootstrap 5 |

## Репозиторий

```
ai-batch-evaluator/
├── manage.py
├── config/                 # settings, Celery, urls, wsgi
├── apps/
│   ├── accounts/           # CustomUser
│   ├── batch/              # Job, Evaluation, UI, DRF /api/
│   ├── evaluators/         # EvaluatorConfig, staff UI
│   └── single/             # один документ
├── pipeline/               # orchestrator, download, extract, llm
├── tasks/                  # evaluate, maintenance, delivery
├── deploy/                 # systemd unit examples
├── rubrics/                # rubric_rus.md, rubric_kaz.md
└── docs/                   # см. docs/README.md
```

## Куда дальше

- Установка: [install.md](install.md)
- Запуск: [run-local.md](run-local.md)
- API: [../reference/api.md](../reference/api.md)
