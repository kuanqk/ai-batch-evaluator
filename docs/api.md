# API Reference

Все эндпоинты, требующие аутентификации, принимают заголовок `X-API-Key`.
Base URL: `http://localhost:8502`
Docs: `http://localhost:8502/docs` (Swagger UI)

---

## Аутентификация

```http
X-API-Key: {EVALUATOR_API_KEY из .env}
```

Возвращает `401` при неверном или отсутствующем ключе.

---

## Батч-обработка

### `POST /batch/upload`
Загрузить CSV/Excel и запустить батч-обработку.

**Auth:** требуется

**Request:** `multipart/form-data`
```
file: <CSV или Excel файл>
name: "ПКС 2025 Алматы"          (опционально, по умолчанию = имя файла)
webhook_url: "https://..."        (опционально)
```

**Response 202:**
```json
{
  "job_id": 42,
  "name": "ПКС 2025 Алматы",
  "total": 3847,
  "status": "running",
  "message": "Батч принят. 3847 файлов поставлено в очередь."
}
```

**Ошибки:**
- `400` — неверный формат файла, отсутствуют колонки `file_path`/`file_url`
- `400` — файл пустой или все строки невалидны

**Валидация CSV перед стартом:**
- Проверяет наличие колонок `file_path`, `file_url`
- Пропускает строки с пустым `file_url`
- Возвращает `skipped_rows` в ответе

---

### `GET /batch/{job_id}`
Прогресс батча.

**Auth:** не требуется

**Response 200:**
```json
{
  "id": 42,
  "name": "ПКС 2025 Алматы",
  "status": "running",
  "total": 3847,
  "processed": 1250,
  "failed": 12,
  "progress_percent": 33.3,
  "avg_score_percentage": 61.4,
  "level_distribution": {"1": 45, "2": 120, "3": 980, "4": 105},
  "created_at": "2025-04-05T10:00:00Z",
  "updated_at": "2025-04-05T11:23:00Z"
}
```

---

### `POST /batch/{job_id}/retry-failed`
Переобработать все failed файлы в батче.

**Auth:** требуется

**Response 200:**
```json
{
  "job_id": 42,
  "requeued": 12,
  "message": "12 задач поставлено в очередь повторно"
}
```

---

### `POST /batch/{job_id}/pause` / `POST /batch/{job_id}/resume`
Приостановить / возобновить обработку батча.

**Auth:** требуется

**Response 200:**
```json
{"job_id": 42, "status": "paused"}
```

---

## Одиночная оценка

### `POST /evaluate`
Оценить один документ (без батча). Асинхронно — возвращает сразу.

**Auth:** требуется

**Request:**
```json
{
  "material_id": 9,
  "file_url": "https://example.com/lesson_plan.docx"
}
```

**Response 202:**
```json
{
  "material_id": 9,
  "eval_id": 1234,
  "status": "accepted",
  "message": "Файл принят для оценки."
}
```

---

## Результаты

### `GET /results`
Таблица результатов с фильтрами и пагинацией.

**Query params:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `job_id` | int | Фильтр по батчу |
| `city` | str | Фильтр по городу |
| `trainer` | str | Фильтр по тренеру |
| `group_name` | str | Фильтр по группе |
| `status` | str | `done`\|`failed`\|`processing`\|`pending` |
| `level` | int | `1`\|`2`\|`3`\|`4` |
| `page` | int | Страница (default=1) |
| `page_size` | int | Размер страницы (default=50, max=200) |

**Response 200:**
```json
{
  "total": 3835,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "id": 1,
      "job_id": 42,
      "city": "Астана",
      "trainer": "Иванов",
      "group_name": "Группа1",
      "file_name": "план.docx",
      "teacher_name": "Сидорова А.В.",
      "topic": "Квадратные уравнения",
      "total_score": 52.0,
      "score_percentage": 69.3,
      "score_level": 3,
      "status": "done",
      "processed_at": "2025-04-05T11:00:00Z"
    }
  ]
}
```

---

### `GET /results/export`
Скачать Excel с результатами (те же фильтры что у `/results`).

**Query params:** те же, что у `/results` (без `page`/`page_size` — экспортируются все)

**Response 200:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

**Колонки Excel:**
| Группа | Колонки |
|--------|---------|
| Мета | ID, Батч, Город, Тренер, Группа, Файл |
| Из документа | ФИО педагога, Тема урока, Язык |
| Результат | Итоговый балл, % выполнения, Уровень, Статус |
| Служебное | Метод извлечения, Символов, Ошибка, Дата обработки |
| Критерии | s1_c1 … s5_c5 (25 колонок) |

---

## Управление оценками

### `GET /api/evaluations/{eval_id}`
Полная информация об одной оценке включая `llm_result`.

**Auth:** требуется

**Response 200:** полный объект evaluation с `llm_result` JSONB.

---

### `POST /api/re-evaluate/{eval_id}`
Перезапустить pipeline для одной оценки.

**Auth:** требуется

**Response 200:**
```json
{"eval_id": 1234, "status": "re-evaluation started"}
```

---

## Мониторинг

### `GET /monitor`
HTML-дашборд мониторинга (браузер). Открытый доступ, auth через JS.

---

### `GET /api/stats`
Агрегированная статистика для дашборда.

**Auth:** требуется

**Response 200:**
```json
{
  "total": 15000,
  "by_status": {"done": 14800, "failed": 120, "processing": 80},
  "avg_processing_seconds": 45.2,
  "avg_score_percentage": 63.1,
  "avg_level": 2.8,
  "level_distribution": {"1": 800, "2": 4200, "3": 7600, "4": 2200},
  "pending_retries": 5
}
```

---

### `GET /api/analytics`
Аналитика: дневной объём, токены, среднее время.

**Auth:** требуется

**Response 200:**
```json
{
  "daily": [{"day": "2025-04-04", "cnt": 842}, {"day": "2025-04-05", "cnt": 1203}],
  "tokens_today": 4820000,
  "tokens_week": 28400000,
  "pipeline": {
    "total_avg_sec": 47.3,
    "cnt": 14800,
    "avg_tokens": 5200
  }
}
```

---

### `GET /health`
Health check. Проверяет PostgreSQL + Redis.

**Response 200:**
```json
{
  "status": "healthy",
  "db": "ok",
  "redis": "ok",
  "timestamp": 1714000000.0
}
```

---

### `GET /stats` (concurrency)
Текущая загрузка семафоров.

**Response 200:**
```json
{
  "llm_calls":   {"max": 5,  "in_use": 3, "available": 2},
  "downloads":   {"max": 20, "in_use": 7, "available": 13},
  "vision_ocr":  {"max": 3,  "in_use": 0, "available": 3}
}
```

---

## AJAX (дашборд)

### `GET /api/job/{job_id}/progress`
Прогресс батча для AJAX-polling (каждые 5 сек пока `status != 'done'`).

**Response 200:** тот же формат что `GET /batch/{job_id}`.
