# AI Batch Evaluator — Обзор

Система массовой автономной оценки учебных планов педагогов с помощью NITEC LLM.

## Цель

Принять CSV/Excel с URL файлов → скачать → извлечь текст → оценить по рубрике (LLM) → сохранить 25 оценок (s1_c1…s5_c5) → выдать результат через UI или API.

## Стек

| Слой | Технология |
|------|-----------|
| Web-фреймворк | Django 4.2 + Gunicorn |
| API | Django REST Framework (TokenAuthentication) |
| БД | PostgreSQL + Django ORM |
| Очереди | Celery 5 + Redis |
| Pipeline | Чистый Python (async) |
| LLM | NITEC LLM API (`openai/gpt-oss-120b`) |
| Vision OCR | `Qwen/Qwen3-VL-235B-A22B-Instruct` (base64 only) |
| UI | Django templates + Bootstrap 5 |

## Документация

- **architecture.md** — компоненты и поток данных
- **database.md** — Django ORM модели и схема БД
- **pipeline.md** — 8 шагов обработки документа
- **api.md** — DRF и browser-UI эндпоинты
- **config.md** — переменные окружения
- **sprints/README.md** — план спринтов

## Репозиторий

```
ai-batch-evaluator/
├── manage.py
├── config/               # Django settings, celery, urls, wsgi
├── apps/
│   ├── accounts/         # CustomUser, auth views
│   └── batch/            # EvaluationJob, Evaluation — ORM, views, API
├── pipeline/             # Чистая Python-логика (без Django)
├── tasks/                # Celery tasks
├── monitoring/           # Трекинг шагов
├── templates/            # Django templates
├── rubrics/              # rubric_rus.md, rubric_kaz.md
└── docs/
```
