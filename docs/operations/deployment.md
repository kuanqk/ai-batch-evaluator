# Orleu Batch Evaluator — План развёртывания и миграции БД

> Индекс всей документации: [docs/README.md](../README.md)

## Принятые решения

| Компонент | Решение | Причина |
|-----------|---------|---------|
| Django + Gunicorn | **systemd на хосте** | LibreOffice уже есть, знакомый подход |
| Celery worker | **systemd на хосте** | Проще дебажить, быстрый деплой |
| PostgreSQL | **Docker контейнер** | Данные в volume, изолировано |
| Redis | **Docker контейнер** | Изолировано от ApeRAG Redis |
| LibreOffice | **хост** | Уже установлен, не тащить в Docker |

---

## Итоговая архитектура

```
Ubuntu Host (192.168.28.9)
│
├── ApeRAG стек (/home/ai/favi/docker-compose.yml)
│   ├── aperag-api          :8000
│   ├── aperag-frontend     :8080
│   ├── aperag-celery
│   ├── aperag-postgres     :5432  → БД: postgres (только ApeRAG)
│   ├── aperag-redis        :6379
│   ├── aperag-qdrant       :6333
│   └── aperag-es           :9200
│
├── Batch Evaluator стек (/opt/orleu-batch-evaluator/)
│   │
│   ├── [systemd] orleu-batch-evaluator.service
│   │   └── gunicorn → Django :8502
│   │
│   ├── [systemd] orleu-batch-celery.service
│   │   └── celery worker (5 воркеров)
│   │
│   └── [Docker] docker-compose.yml
│       ├── batch-postgres  :5433
│       │   ├── orleu_batch_evaluator  ← Batch Evaluator
│       │   └── evaluator_db           ← AI Evaluator (перенос)
│       └── batch-redis     :6380
│
├── AI Evaluator (/opt/orleu-evaluator/)
│   └── [Docker] evaluator  :8081
│       └── DATABASE_URL → localhost:5433/evaluator_db
│
└── LibreOffice (хост) — используется Celery напрямую
```

---

## Деплой

```bash
# На локальной машине
git push origin main

# На сервере
cd /opt/orleu-batch-evaluator
git pull origin main
source venv/bin/activate
pip install -r requirements.txt  # если новые зависимости
python manage.py migrate
sudo systemctl restart orleu-batch-evaluator
sudo systemctl restart orleu-batch-celery
```

---

## docker-compose.yml (только БД и Redis)

```yaml
version: '3.8'

services:
  batch-postgres:
    image: postgres:16
    container_name: batch-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - batch-postgres-data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    restart: always

  batch-redis:
    image: redis:7-alpine
    container_name: batch-redis
    ports:
      - "6380:6379"
    restart: always

volumes:
  batch-postgres-data:
```

---

## systemd сервисы

Готовые unit-файлы лежат в репозитории: **`deploy/orleu-batch-evaluator.service`** и **`deploy/orleu-batch-celery.service`**.

- Gunicorn: `--timeout 120` (долгие запросы).
- Celery: очереди **`-Q evaluation,maintenance`** — должны совпадать с `CELERY_TASK_ROUTES` в `config/settings.py`.

Установка:

```bash
sudo cp deploy/orleu-batch-evaluator.service /etc/systemd/system/
sudo cp deploy/orleu-batch-celery.service /etc/systemd/system/
# при необходимости поправить User/Group/пути в файлах
sudo systemctl daemon-reload
```

---

## .env конфигурация

Django читает **`DATABASE_URL`** и **`DJANGO_SECRET_KEY`** (см. `config/settings.py`). Скопируйте `.env.example` и заполните.

**Пример для сервера** (Postgres и Redis в Docker на портах 5433 и 6380):

```env
DJANGO_SECRET_KEY=длинный-случайный-ключ
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1,your.domain.com

# Одна строка (как в приложении)
DATABASE_URL=postgresql://postgres:ВАШ_ПАРОЛЬ@localhost:5433/orleu_batch_evaluator

REDIS_URL=redis://localhost:6380/1

NITEC_API_KEY=sk-xxx
NITEC_BASE_URL=https://llm.nitec.kz/v1
NITEC_MODEL=openai/gpt-oss-120b
NITEC_VISION_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
NITEC_MAX_TOKENS=4096
NITEC_MAX_WORKERS=5
MAX_CONCURRENT_DOWNLOADS=20
MAX_CONCURRENT_VISION=3

MIN_TEXT_CHARS=50
VISION_MAX_PAGES=10
VISION_DPI=150

TMP_DIR=/opt/orleu-batch-evaluator/tmp
REPORTS_DIR=/opt/orleu-batch-evaluator/reports
RUBRICS_DIR=/opt/orleu-batch-evaluator/rubrics
```

**Доставка результатов** (Beles / webhook) настраивается в **EvaluatorConfig** в админке/UI: после успешной оценки вызывается `tasks/delivery.py` (ретраи по полям `enable_retry` / `retry_attempts`).

---

## Продакшен (краткий чеклист)

- **DEBUG=false**, `DJANGO_SECRET_KEY` уникальный и не в git.
- **ALLOWED_HOSTS** — домены за Nginx, не `*` в проде.
- **HTTPS** — терминация TLS на Nginx, к приложению можно HTTP локально.
- Перед **`migrate`** на проде — **бэкап БД** (`pg_dump`).
- Секреты API (NITEC, Beles, входящие ключи конфигов) — только в `.env` или секрет-хранилище.

---

## Порядок развёртывания

### Фаза 1 — Развернуть Batch Evaluator (без переноса БД)

```bash
# 1. Создать папку
sudo mkdir -p /opt/orleu-batch-evaluator
sudo chown ai:ai /opt/orleu-batch-evaluator

# 2. Клонировать репозиторий
cd /opt/orleu-batch-evaluator
git clone https://gitlab.orleu.edu.kz/ai-infra/orleu-batch-evaluator.git .

# 3. Создать venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Поднять БД и Redis
docker compose up -d batch-postgres batch-redis

# 5. Создать БД
docker exec batch-postgres psql -U postgres -c "
CREATE DATABASE orleu_batch_evaluator;
"

# 6. Миграции и суперпользователь
python manage.py migrate
python manage.py createsuperuser

# 7. Установить systemd сервисы
sudo cp deploy/orleu-batch-evaluator.service /etc/systemd/system/
sudo cp deploy/orleu-batch-celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orleu-batch-evaluator orleu-batch-celery
sudo systemctl start orleu-batch-evaluator orleu-batch-celery

# 8. Проверить
systemctl status orleu-batch-evaluator
systemctl status orleu-batch-celery
curl http://localhost:8502/
```

### Фаза 2 — Перенос evaluator_db (отдельно, после стабилизации)

```bash
# 1. Резервная копия (ОБЯЗАТЕЛЬНО!)
docker exec aperag-postgres pg_dump -U postgres evaluator_db \
  > /opt/backups/evaluator_db_$(date +%Y%m%d_%H%M%S).sql

# 2. Остановить AI Evaluator (downtime ~10 минут)
cd /opt/orleu-evaluator && docker compose stop evaluator

# 3. Создать БД в batch-postgres
docker exec batch-postgres psql -U postgres -c "
CREATE USER evaluator WITH PASSWORD 'password';
CREATE DATABASE evaluator_db OWNER evaluator;
GRANT ALL PRIVILEGES ON DATABASE evaluator_db TO evaluator;
"

# 4. Восстановить дамп
cat /opt/backups/evaluator_db_*.sql | \
  docker exec -i batch-postgres psql -U postgres -d evaluator_db

# 5. Проверить перенос
docker exec batch-postgres psql -U postgres -d evaluator_db -c "
SELECT COUNT(*), status FROM evaluations GROUP BY status;
"

# 6. Обновить .env AI Evaluator
# DATABASE_URL=postgresql://evaluator:password@localhost:5433/evaluator_db

# 7. Запустить AI Evaluator
cd /opt/orleu-evaluator && docker compose up -d evaluator

# 8. Проверить
curl http://localhost:8081/health

# 9. После нескольких дней работы — удалить старую БД
docker exec aperag-postgres psql -U postgres -c "DROP DATABASE evaluator_db;"
```

---

## Управление сервисами

```bash
# Статус
systemctl status orleu-batch-evaluator
systemctl status orleu-batch-celery

# Рестарт
sudo systemctl restart orleu-batch-evaluator
sudo systemctl restart orleu-batch-celery

# Логи
journalctl -u orleu-batch-evaluator -f
journalctl -u orleu-batch-celery -f

# Docker БД и Redis
cd /opt/orleu-batch-evaluator
docker compose ps
docker compose restart batch-postgres
docker compose restart batch-redis
```

---

## Чеклист

### Фаза 1 — Batch Evaluator
- [ ] Код готов и протестирован
- [ ] GitLab репозиторий создан
- [ ] `.env` заполнен
- [ ] `docker compose up -d batch-postgres batch-redis` — запущено
- [ ] `python manage.py migrate` — выполнено
- [ ] systemd сервисы установлены и запущены
- [ ] Nginx настроен администратором (`airavaluator.orleu.edu.kz → :8502`)
- [ ] Первый тестовый батч прошёл успешно

### Фаза 2 — Перенос evaluator_db
- [ ] Резервная копия сделана
- [ ] Выбрано время с минимальной нагрузкой
- [ ] AI Evaluator остановлен
- [ ] Дамп восстановлен в batch-postgres
- [ ] AI Evaluator запущен с новым DATABASE_URL
- [ ] Проверена работа через дашборд `/monitor`
- [ ] Через несколько дней — удалена старая БД из aperag-postgres

---

## Открытые вопросы

- [ ] Когда планируется объединение AI Evaluator → модуль Batch Evaluator?
- [ ] Нужен ли новый домен или использовать `airavaluator.orleu.edu.kz`?
- [ ] Бэкапы — настроить cron для автоматического дампа?
