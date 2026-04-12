# API Reference

Базовый URL (dev): `http://localhost:8502`  
Префикс JSON API: **`/api/`** (см. `apps/batch/api_urls.py`).

В этом проекте **нет** встроенного Swagger/OpenAPI UI (`/docs`).

---

## Аутентификация

### Глобальные эндпоинты `/api/...` (кроме health)

Используется **Django REST Framework**: сессия браузера или **`Authorization: Token <token>`** (REST Token, пользователь в админке).

Дополнительно: если в `.env` задан **`EVALUATOR_API_KEY`**, для защищённых view нужен заголовок:

```http
X-API-Key: <значение EVALUATOR_API_KEY>
```

Если `EVALUATOR_API_KEY` пустой — проверка ключа отключена (остаётся только вход по Token/сессии).

### Per-config API `/api/ev/<slug>/...`

Отдельный ключ на конфигурацию: **`X-API-Key`** должен совпадать с полем **`EvaluatorConfig.api_key`** для данного `slug`. Конфиг должен быть **`is_active=True`**.  
Аутентификация Django для этих маршрутов **не** используется.

---

## Per-config (Beles и др.)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/ev/<slug>/evaluate/` | Один документ: `{ "file_url", "material_id"? }` → 202 |
| POST | `/api/ev/<slug>/batch/` | Multipart CSV/Excel как у глобального batch upload |
| GET | `/api/ev/<slug>/health/` | DB + Redis, без API-ключа |
| GET | `/api/ev/<slug>/stats/` | Лимиты конфига + глобальные настройки, с `X-API-Key` |

---

## Батч-обработка

### `POST /api/batch/upload/`

**Auth:** да (см. выше)

**Body:** `multipart/form-data`

- `file` — CSV или Excel
- `name` — опционально
- `webhook_url` — опционально (POST при завершении job с агрегатами)

**Ответ 202:** `job_id`, `name`, `total`, `status`, `message`, `skipped_rows`.

**Ошибки 400:** нет колонок `file_path`/`file_url`, пустой файл, нет валидных строк.

---

### `GET /api/batch/<job_id>/`

**Auth:** нет (как в коде)

Прогресс батча: `processed`, `failed`, `total`, `progress_percent`, средний балл, распределение по уровням и т.д.

---

### `POST /api/batch/<job_id>/retry-failed/`

**Auth:** да

Повторная постановка в очередь для записей со статусом failed.

---

### `POST /api/batch/<job_id>/pause/` · `POST /api/batch/<job_id>/resume/`

**Auth:** да

---

## Одиночная оценка (глобальный Beles-стиль)

### `POST /api/evaluate/`

**Auth:** да

**JSON:** `{ "file_url", "material_id"? }`  
**202:** `eval_id`, `material_id`, `status: "accepted"`.

Без привязки к `EvaluatorConfig` (в отличие от `/api/ev/<slug>/evaluate/`).

---

## Результаты

### `GET /api/evaluations/`

**Auth:** да

**Query:** `job_id`, `status`, `city`, `level`, `page`, `page_size`.

**Ответ:** `{ "count", "page", "results": [...] }`.

---

### `GET /api/evaluations/<eval_id>/`

**Auth:** да  

Одна оценка (сериализатор DRF).

---

### `POST /api/evaluations/<eval_id>/retry/`

**Auth:** да  

Повтор pipeline для `failed` или `pending`. **202/200:** `requeued` (см. реализацию).

---

## Статистика и health

### `GET /api/stats/`

**Auth:** да  

Сводка: `total_jobs`, `total_evaluations`, `done`, `failed`, `avg_score_percentage`, `level_distribution`.

---

### `GET /api/health/`

**Auth:** не требуется  

`status`, `db`, `redis`. HTTP **503**, если БД недоступна.

---

## Браузерный UI (не JSON API)

| Путь | Назначение |
|------|------------|
| `/batch/` | Дашборд батчей |
| `/batch/upload/` | Загрузка CSV |
| `/batch/results/` | Таблица результатов |
| `/batch/results/export/` | Excel |
| `/evaluators/` | Конфигурации оценщика (staff) |
| `/single/` | Один документ (форма) |

Прогресс батча на дашборде — **серверный рендер**, отдельного `GET /api/job/.../progress/` в проекте нет.
