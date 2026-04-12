# Документация Orleu Batch Evaluator

Индекс разбит по темам — открывайте только нужный файл (удобно для ревью и ИИ).

## Быстрый старт

| Документ | Содержание |
|----------|------------|
| [getting-started/overview.md](getting-started/overview.md) | Цель продукта, стек, дерево репозитория |
| [getting-started/install.md](getting-started/install.md) | Зависимости, venv, первичный `.env` |
| [getting-started/run-local.md](getting-started/run-local.md) | Docker, `make`, Celery |

## Архитектура

| Документ | Содержание |
|----------|------------|
| [architecture/system.md](architecture/system.md) | Компоненты, поток данных, Docker Compose |
| [architecture/auth.md](architecture/auth.md) | Session, Token, `X-API-Key`, per-config API |
| [architecture/concurrency.md](architecture/concurrency.md) | Celery, `asyncio.run`, семафоры, очереди |

## Справочник

| Документ | Содержание |
|----------|------------|
| [reference/api.md](reference/api.md) | REST `/api/…`, per-config `/api/ev/<slug>/…`, UI |
| [reference/config-env.md](reference/config-env.md) | Переменные окружения |
| [reference/database.md](reference/database.md) | Модели, атомарные счётчики |
| [reference/pipeline.md](reference/pipeline.md) | Шаги обработки файла |

## Эксплуатация

| Документ | Содержание |
|----------|------------|
| [operations/deployment.md](operations/deployment.md) | Сервер, systemd, docker-compose БД/Redis, фазы |
| [operations/backup-migrate.md](operations/backup-migrate.md) | Бэкап PostgreSQL, миграции в проде |
| [operations/troubleshooting.md](operations/troubleshooting.md) | Логи, очередь Celery, типичные сбои |

## Планы и прочее

| Документ | Содержание |
|----------|------------|
| [plans/improvements.md](plans/improvements.md) | Долгосрочный план фич (мультиконфиг, pipeline) |
| [sprints/README.md](sprints/README.md) | Спринты и статус (**не архив** — живая история проекта) |
| [archive/README.md](archive/README.md) | Редиректы и [архивная база знаний](archive/orleu-batch-evaluator-knowledge-base.md) |

## Архив

Перенесённые заглушки и длинный **knowledge base** — в **[archive/](archive/)** (см. [archive/README.md](archive/README.md)). Корневой файл [orleu-batch-evaluator-knowledge-base.md](orleu-batch-evaluator-knowledge-base.md) — короткий редирект.
