# Sprint 5 — apps/single + Tests ✅

**Статус:** ЗАВЕРШЁН

## Что сделано

### apps/single — Single-document evaluation

Browser UI для оценки одного документа (ранее — `orleu-evaluator-main` без ApeRAG):

- `apps/single/views.py`:
  - `submit` — форма с URL и optional material_id → создаёт Job + Evaluation → `process_file.delay()`
  - `result` — показывает статус, баллы по критериям, feedback, teacher/topic
- `apps/single/urls.py` — `GET/POST /single/`, `GET /single/<eval_id>/`
- Шаблоны: `templates/single/submit.html`, `templates/single/result.html`
  - Авторедирект через `setTimeout` пока статус processing/pending
  - Таблица баллов по 5 разделам × 5 критериев с цветовой индикацией

### Интеграция

- Добавлен `apps.single` в `INSTALLED_APPS`
- Добавлен `path("single/", include("apps.single.urls"))` в root URLconf
- Добавлена ссылка "Один документ" в sidebar навигации

### Tests (35 тестов, все прошли)

**`tests/test_models.py`** — Django ORM (SQLite in-memory):
- Создание EvaluationJob / Evaluation
- `progress_percent` при разных значениях
- Атомарный `F('processed') + 1`
- Atomic claim (двойной claim блокируется)
- Evaluation без Job (single mode)

**`tests/test_pipeline_utils.py`** — без БД:
- `parse_batch_upload`: CSV базовый, пропуск пустых URL, BOM UTF-8, отсутствие колонок, короткий путь
- `parse_file_path`: нормальный путь, backslash, слишком короткий
- `parse_llm_response`: plain JSON, markdown fence, think-block, None/empty
- `extract_scores`: пустой, с данными
- `_level_from_points`: граничные значения

**`tests/test_views.py`** — Django test client:
- Auth: login page, POST login, dashboard redirect без auth
- Dashboard: пустой, с заданиями
- Results: пустой, с фильтром job_id
- API `/api/health/`
- API auth required (401/403)
- Single: submit страница, result 404

### Infrastructure

- `config/test_settings.py` — переопределяет DB → SQLite `:memory:`
- `pytest.ini` — `DJANGO_SETTINGS_MODULE = config.test_settings`
- `conftest.py` — пустой (переопределение через test_settings)
- `requirements.txt` — добавлены `pytest>=8.0.0`, `pytest-django>=4.8.0`

## Команды

```bash
python -m pytest tests/ -v    # все тесты
python -m pytest tests/test_models.py -v   # только модели
python -m pytest tests/test_pipeline_utils.py -v  # только pipeline
```
