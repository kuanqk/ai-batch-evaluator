# Orleu Batch Evaluator — База знаний

> Система массовой оценки учебных материалов педагогов на базе Django + Celery + NITEC LLM.  
> Сервер: `/opt/orleu-batch-evaluator/` | Домен: `airavaluator.orleu.edu.kz:8502`

**Актуальный индекс:** [`../README.md`](../README.md). Справочник: `docs/reference/`, архитектура: `docs/architecture/`, деплой: `docs/operations/deployment.md`.  
Ниже — сжатая база знаний; при расхождении с кодом приоритет у репозитория и структурированной документации.

---

## Содержание

1. [Архитектура системы](#архитектура-системы)
2. [Стек технологий](#стек-технологий)
3. [Структура проекта](#структура-проекта)
4. [Модели базы данных](#модели-базы-данных)
5. [Pipeline обработки файлов](#pipeline-обработки-файлов)
6. [Celery задачи](#celery-задачи)
7. [LLM интеграция](#llm-интеграция)
8. [Рубрика оценивания](#рубрика-оценивания)
9. [API и маршруты](#api-и-маршруты)
10. [Конфигурация (.env)](#конфигурация-env)
11. [Деплой и запуск](#деплой-и-запуск)
12. [Авторизация и роли](#авторизация-и-роли)
13. [Входные данные](#входные-данные)
14. [Экспорт результатов](#экспорт-результатов)
15. [Известные ограничения и решения](#известные-ограничения-и-решения)

---

## Архитектура системы

```
Пользователь (браузер)
        │
        ▼
 Django Web (Gunicorn :8502)
        │
        ├── Загрузка CSV/Excel → создание EvaluationJob + Evaluation записей
        │
        └── Celery Task Queue (Redis :6379)
                │
                └── 5 параллельных воркеров
                        │
                        ├── downloader.py  → скачать файл (OneDrive / Google Docs / URL)
                        ├── converter.py   → LibreOffice → docx/pdf где нужно
                        ├── extractor.py   → текст: docx XML / PyMuPDF / Vision (Qwen3-VL)
                        ├── llm.py         → NITEC LLM оценка по рубрике
                        └── → сохранить результат в PostgreSQL (опц. delivery → Beles/webhook)
```

Проект полностью независим от ApeRAG — собственный pipeline без внешних зависимостей от других сервисов Orleu.

---

## Стек технологий

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Веб-фреймворк | Django | 4.2.x |
| Фоновые задачи | Celery | 5.3.x |
| Брокер очереди | Redis | :6379 (уже на сервере) |
| База данных | PostgreSQL | :5432 (уже на сервере) |
| WSGI сервер | Gunicorn | 3 воркера |
| Конвертация документов | LibreOffice (headless) | уже установлен |
| Текст из PDF | PyMuPDF (`fitz`) | страница за страницей |
| OCR (мало текста в PDF) | Qwen3-VL через NITEC (PNG base64) | не DeepSeek-OCR |
| LLM оценка | NITEC LLM (llm.nitec.kz/v1) | openai/gpt-oss-120b |
| Экспорт Excel | openpyxl | 3.1.x |
| Определение языка | langdetect | 1.0.9 |
| HTTP клиент | requests | 2.31.x |
| LLM клиент | openai SDK | 1.51.x |

---

## Структура проекта

```
/opt/orleu-batch-evaluator/
├── manage.py
├── .env                          # секреты (не в git)
├── .env.example                  # шаблон конфигурации
├── requirements.txt
├── venv/
│
├── config/                       # Django настройки
│   ├── __init__.py               # подключение Celery
│   ├── settings.py               # все настройки
│   ├── celery.py                 # Celery app
│   ├── urls.py                   # корневые URL
│   └── wsgi.py
│
├── apps/
│   ├── batch/                    # EvaluationJob, Evaluation, UI, DRF api.py
│   ├── evaluators/               # EvaluatorConfig, рубрики, staff UI
│   ├── accounts/                 # CustomUser
│   └── single/                   # один документ (форма)
│
├── pipeline/                     # async-логика (orchestrator, downloader, …)
│   ├── orchestrator.py
│   ├── downloader.py
│   ├── converter.py
│   ├── extractor.py
│   ├── validator.py
│   ├── llm.py
│   ├── rubric_loader.py
│   └── parser.py
│
├── tasks/                        # Celery: evaluate.py, maintenance.py, delivery.py
│
├── rubrics/                      # rubric_rus.md, rubric_kaz.md (дефолт)
│
├── deploy/
│   ├── orleu-batch-evaluator.service   # systemd: Gunicorn
│   └── orleu-batch-celery.service      # systemd: Celery worker
│
└── tmp/                          # временные файлы (автоматически удаляются)
```

---

## Модели базы данных

### EvaluationJob — батч-задание

Создаётся при загрузке CSV/Excel. Хранит агрегированную статистику по батчу.

```python
class EvaluationJob(models.Model):
    name         # CharField     — "ПКС 2025 Алматы"
    source_file  # CharField     — имя загруженного файла
    total        # IntegerField  — всего файлов в батче
    processed    # IntegerField  — обработано (включая failed)
    failed       # IntegerField  — с ошибками
    status       # CharField     — pending / running / done / failed
    created_at   # DateTimeField
    updated_at   # DateTimeField

    # Вычисляемые свойства:
    progress_percent  # (processed + failed) / total * 100
    success_count     # processed - failed
```

**Статусы Job:** `pending` → `running` → `done`

### Evaluation — один файл

Создаётся для каждой строки входного CSV. Хранит источник, результат LLM и статус.

```python
class Evaluation(models.Model):
    job          # ForeignKey(EvaluationJob)

    # Источник (парсится из file_path)
    file_path    # "ПКС2025/Астана/Тренер_Иванов/Группа1/план.docx"
    file_url     # URL для скачивания
    city         # "Астана"
    trainer      # "Иванов"
    group        # "Группа 1"
    file_name    # "план.docx"

    # Извлекается LLM из документа
    teacher_name # ФИО педагога (или null)
    topic        # Тема урока (или null)

    # Результат оценки
    scores       # JSONField: {"s1_c1": 3, "s1_c2": 2, ..., "s5_c5": 1}
    total_score  # FloatField: сумма баллов (max 75)
    level        # IntegerField: 1–4
    feedback     # TextField: сильные стороны + зоны роста + рекомендация
    raw_response # TextField: сырой JSON ответ LLM

    # Статус и мета
    status       # pending / processing / done / failed
    error        # текст ошибки если failed
    created_at
    processed_at
```

**Статусы Evaluation:** `pending` → `processing` → `done` / `failed`

**Ключи в `scores`:** формат `s{раздел}_c{критерий}`, например `s1_c1` ... `s5_c5` (всего 25 ключей).

---

## Pipeline обработки файлов

Цепочка задаётся в `pipeline/orchestrator.py` (`run_pipeline`) и вызывается из Celery `tasks/evaluate.py` через `asyncio.run`.

Упрощённо:

1. **Скачивание** — `downloader.download_file` (опц. Google Docs → export URL).
2. **Конвертация** — `converter.convert_to_docx` (LibreOffice для `.doc` и т.д.).
3. **Валидация** — `validator.check_truncated_zip`, `fix_broken_docx` при необходимости.
4. **Текст** — `extractor.extract_text`: docx (XML/таблицы) → при малом объёме PyMuPDF → при необходимости Vision (Qwen3-VL, PNG base64 по страницам). Пороги: `MIN_TEXT_CHARS`, `VISION_*` из `.env` или `EvaluatorConfig`.
5. **LLM** — `llm.evaluate_with_llm`; рубрика из файлов `rubrics/` или из модели `Rubric` при мультиконфиге.

Подробно: **`docs/reference/pipeline.md`**.

**Пауза батча:** при `job.paused` задача `process_file` уходит в retry (см. `tasks/evaluate.py`).

---

## Celery задачи

### `process_job(job_id)`

Точка входа для батча: ставит в очередь `process_file` для каждой оценки. См. `tasks/evaluate.py`.

```python
from tasks.evaluate import process_job
process_job.delay(job.id)
```

### `process_file(evaluation_id)`

Полный pipeline для одного файла. Декоратор: `bind=True`, большой `max_retries` для паузы батча.

**Запуск воркеров (очереди как в `CELERY_TASK_ROUTES`):**
```bash
celery -A config worker --concurrency=5 -Q evaluation,maintenance -l info
```

Семафоры LLM/скачиваний/Vision — `config/concurrency.py` и переменные `NITEC_MAX_WORKERS`, `MAX_CONCURRENT_DOWNLOADS`, `MAX_CONCURRENT_VISION`.

---

## LLM интеграция

### NITEC API

- **Endpoint:** `https://llm.nitec.kz/v1` (OpenAI-совместимый)
- **Клиент:** `openai` SDK с `base_url=NITEC_BASE_URL`
- **Основная модель:** `openai/gpt-oss-120b`

### Доступные модели NITEC

| Модель | Назначение |
|--------|-----------|
| `openai/gpt-oss-120b` | **Основная** — оценка планов уроков |
| `deepseek-ai/DeepSeek-V3.2` | Альтернатива (лучше для рус/каз текстов) |
| `moonshotai/Kimi-K2.5` | Альтернатива |
| `deepseek-ai/DeepSeek-OCR` | Не использовать для текста (bbox, не содержимое) |
| `Qwen/Qwen3-VL-235B-A22B-Instruct` | Vision OCR (страницы PDF → PNG → API) |
| `BAAI/bge-m3` | Embedding |
| `astanahub/alemllm` | Казахстанская LLM |

Модель меняется через переменную `NITEC_MODEL` в `.env` — перезапуск не нужен, значение читается при каждом запросе.

### Структура JSON ответа LLM

```json
{
  "validation": {
    "is_valid": true,
    "is_substantive": true,
    "is_on_topic": true,
    "failure_reason": null
  },
  "teacher_name": "Иванова Айгуль Сериковна",
  "topic": "Решение квадратных уравнений",
  "full_report": {
    "overall_score": {
      "total_points": 52,
      "max_points": 75,
      "percentage": 69.3,
      "level": 3
    },
    "sections": [
      {
        "section_number": 1,
        "section_title": "Представление материала в понятной форме",
        "criteria": [
          {
            "criterion_number": 1,
            "criterion_title": "...",
            "score": 2,
            "evidence_quote": "цитата из документа",
            "justification": "обоснование",
            "recommendation": "рекомендация"
          }
        ]
      }
    ],
    "top_strengths": ["сильная сторона 1", "сильная сторона 2"],
    "critical_gaps": ["пробел 1", "пробел 2"]
  },
  "brief_report_json": {
    "sections": [{"section_number": 1, "section_title": "...", "score": 10, "max_score": 15}],
    "overall_recommendation": "общая рекомендация"
  },
  "level_assessment": {
    "level": 3,
    "description": "Уровень 3 — продвинутый",
    "justification": "обоснование"
  }
}
```

### Парсинг ответа

`parse_llm_response()` обрабатывает три случая:
1. Чистый JSON → `json.loads()`
2. JSON в Markdown-блоке ` ```json ... ``` ` → strip + `json.loads()`
3. JSON где-то в тексте → `re.search(r'\{.*\}', text, re.DOTALL)` + `json.loads()`

### Извлечение оценок

`extract_scores()` возвращает `(scores_dict, total_score, level)`:
- `scores_dict` = `{"s1_c1": 3, "s1_c2": 2, ..., "s5_c5": 1}` — 25 ключей
- Ключи формируются как `s{section_number}_c{criterion_number}`

---

## Рубрика оценивания

Файлы по умолчанию: каталог **`RUBRICS_DIR`** (в репозитории `rubrics/`, см. `rubric_rus.md` / `rubric_kaz.md`). В мультиконфиге возможны загрузки в БД (`evaluators.Rubric`).

### Структура (5 разделов × 5 критериев = 25 критериев)

| № | Раздел |
|---|--------|
| 1 | Представление материала в понятной форме |
| 2 | Вовлечение обучающихся в деятельность, представляющую вызов |
| 3 | Предоставление обратной связи в поддержку обучения |
| 4 | Практика и применение изученного |
| 5 | Адаптация преподавания к различным потребностям учащихся |

**Шкала:** 0–3 балла за каждый критерий. **Максимум: 75 баллов.**

### Шкала уровней

| Уровень | Диапазон % | Диапазон баллов |
|---------|-----------|-----------------|
| 1 | 0–25% | 0–18 |
| 2 | 26–50% | 19–37 |
| 3 | 51–75% | 38–56 |
| 4 | 76–100% | 57–75 |

### Определение языка документа

```python
# pipeline/rubric_loader.py
from langdetect import detect

def get_rubric(text: str) -> str:
    lang = detect(text[:500])   # "kk" или "ru"
    path = RUBRIC_KAZ if lang == "kk" else RUBRIC_RUS
    with open(path, encoding='utf-8') as f:
        return f.read()
```

Если `langdetect` выбрасывает исключение — используется русская рубрика по умолчанию.

---

## API и маршруты

**Браузер:** `/batch/` (дашборд, upload, results, export), `/evaluators/…`, `/single/…`, `/accounts/login/`.

**JSON API:** префикс `/api/` — см. **`docs/reference/api.md`**. Примеры: `POST /api/batch/upload/`, `GET /api/batch/<id>/`, `GET /api/evaluations/`, `GET /api/health/`, per-config `POST /api/ev/<slug>/evaluate/`.

Отдельного `GET /api/job/<id>/progress/` в проекте **нет**; прогресс на дашборде — серверный рендер.

### Фильтры на странице Results

GET-параметры и экспорт — как в `apps/batch/views.py` (см. `docs/reference/api.md`).

---

## Конфигурация (.env)

Используется **`DATABASE_URL`**, **`DJANGO_SECRET_KEY`**, **`REDIS_URL`**, NITEC-переменные, **`RUBRICS_DIR`**, опционально **`EVALUATOR_API_KEY`**. Полный список: **`docs/reference/config-env.md`** и **`/.env.example`**.

**Смена модели LLM** — `NITEC_MODEL` в `.env` (для режима без `EvaluatorConfig`); в мультиконфиге модель задаётся в `EvaluatorConfig`.

---

## Деплой и запуск

### Первичный деплой

Клонирование репозитория, venv, `pip install -r requirements.txt`, `migrate`, unit-файлы из **`deploy/`** — пошагово **`docs/operations/deployment.md`**.

### Ручной запуск (разработка)

```bash
cd /opt/orleu-batch-evaluator
source venv/bin/activate

# Terminal 1 — Django
python manage.py runserver 0.0.0.0:8502

# Terminal 2 — Celery
celery -A config worker --concurrency=5 -Q evaluation,maintenance -l info
```

### Управление сервисами

```bash
# Статус
systemctl status orleu-batch-evaluator
systemctl status orleu-batch-celery

# Рестарт
systemctl restart orleu-batch-evaluator
systemctl restart orleu-batch-celery

# Логи
journalctl -u orleu-batch-celery -f
tail -f /var/log/orleu-batch-evaluator/celery.log
tail -f /var/log/orleu-batch-evaluator/error.log
```

### Миграции

```bash
source venv/bin/activate
python manage.py makemigrations evaluator
python manage.py migrate
```

---

## Авторизация и роли

Используется стандартный **Django Auth** (сессии + CSRF).

| Роль | Права | Как создать |
|------|-------|-------------|
| `admin` (superuser) | Все страницы, загрузка батчей, запуск, Admin | `createsuperuser` или `deploy.sh` |
| `analyst` | Только `/results/` + экспорт Excel | Создать в `/admin/`, без staff/superuser флагов |

Все страницы защищены `@login_required`. Неавторизованные запросы перенаправляются на `/login/`.

**Сброс пароля:**
```bash
source venv/bin/activate
python manage.py changepassword admin
```

---

## Входные данные

### Формат CSV

```csv
file_path,file_url
ПКС2025/Астана/Иванов/Группа1/план.docx,https://onedrive.live.com/...
ПКС2025/Алматы/Касымов/Группа2/урок.docx,https://onedrive.live.com/...
```

### Формат Excel (.xlsx / .xls)

Первая строка — заголовки. Обязательные колонки: `file_path`, `file_url`.

### Парсинг пути

```
ПКС2025 / Астана / Иванов / Группа1 / план.docx
  [0]      [1]      [2]      [3]       [4]
           city   trainer   group   file_name
```

Реализовано в `pipeline/parser.py`. Поддерживает как прямые слэши, так и обратные.

### OneDrive ссылки

`downloader.py` автоматически преобразует sharing URLs:
- `1drv.ms/...` → добавляет `?download=1`
- `sharepoint.com/...` → добавляет `&download=1`
- `onedrive.live.com/...` → добавляет `?download=1`

> ⚠️ Если прямое скачивание не работает — возможно потребуется интеграция через Microsoft Graph API. Это открытый вопрос проекта.

---

## Экспорт результатов

URL: `GET /batch/results/export/` (см. `apps/batch/urls.py`).

**Колонки Excel:**

| Группа | Колонки |
|--------|---------|
| Мета | ID, Батч, Город, Тренер, Группа, Файл |
| Из документа | ФИО педагога, Тема урока |
| Результат | Итоговый балл, Уровень, Статус |
| Служебное | Ошибка, Дата обработки |
| Критерии | s1_c1 ... s5_c5 (25 колонок) |

Заголовки выделены синим фоном с белым текстом. Ширина колонок подстраивается автоматически (max 40 символов).

---

## Известные ограничения и решения

### Счётчики processed/failed в EvaluationJob

Инкременты делаются через **`F()`** атомарно (см. `tasks/evaluate.py` и `docs/reference/database.md`).

### Сканированные / «пустые» PDF

Если после PyMuPDF текста мало — при включённом Vision вызывается **Qwen3-VL** по страницам (дорого по токенам). Пороги: `MIN_TEXT_CHARS`, `VISION_MAX_PAGES`, `VISION_DPI`.

### Контекстное окно LLM

Средний план урока — 2000–5000 токенов. Рубрика — ~1500 токенов. Итого ~6500 токенов на запрос. Лимит модели — 32k токенов. При очень длинных документах возможна обрезка — нужен мониторинг.

### Rate limit NITEC

Текущий лимит: 5 параллельных воркеров. Значение подобрано эмпирически. Если появляются ошибки 429 — уменьшить `NITEC_MAX_WORKERS` в `.env` и рестартовать Celery.

### OneDrive Graph API

Прямое скачивание через `?download=1` работает только для публично доступных файлов. Для закрытых папок потребуется:
- Регистрация приложения в Azure AD
- OAuth2 flow с Microsoft Graph API
- Это открытый вопрос проекта

---

## Типичные команды для отладки

```bash
# Проверить очередь Celery
celery -A config inspect active

# Посмотреть все pending задачи
celery -A config inspect reserved

# Принудительно завершить все задачи
celery -A config purge

# Интерактивная оболочка Django
python manage.py shell

# Проверить Job вручную
python manage.py shell -c "
from apps.batch.models import EvaluationJob
job = EvaluationJob.objects.last()
print(job.name, job.status, job.progress_percent)
"

# Запустить один файл вручную (без Celery)
python manage.py shell -c "
from tasks.evaluate import process_file
process_file(123)  # или .delay(123) для очереди
"
```
