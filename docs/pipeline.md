# Pipeline обработки файла

Файл: `tasks/evaluate.py` → `pipeline/*`

Каждый файл проходит 8 шагов в Celery задаче `process_file(eval_id)`.
При старте шага: `evaluation.current_step = N`, `evaluation.status = 'processing'`.
При ошибке: `evaluation.status = 'failed'`, `evaluation.error = str(e)`, `job.failed += 1`.

---

## Шаг 1: Скачивание файла

**Файл:** `pipeline/downloader.py`

```python
async def download_file(url: str) -> tuple[bytes, str]:
    """Возвращает (content_bytes, filename)"""
```

Логика:
1. **OneDrive:** `1drv.ms/*` → `?download=1`; `sharepoint.com/*` → `&download=1`; `onedrive.live.com/*` → `?download=1`
2. **Google Docs:** `/document/d/{id}/` → `/export?format=pdf`
3. **Прямые ссылки:** GET с `follow_redirects=True`
4. Имя файла: из `Content-Disposition` → из URL → `document.pdf`
5. Таймаут: 60 сек. Ограничение: `download_semaphore` (20 параллельных)

> ⚠️ OneDrive sharing URL работает только для **публично доступных** файлов.
> Для закрытых папок → нужен Microsoft Graph API (открытый вопрос).

---

## Шаг 2: Конвертация форматов

**Файл:** `pipeline/converter.py`

```python
async def convert_to_docx(content: bytes, filename: str) -> tuple[bytes, str]:
    """doc → docx через LibreOffice (async subprocess). catdoc fallback."""

async def convert_docx_to_pdf(content: bytes) -> Optional[bytes]:
    """docx → pdf через LibreOffice. Нужен для Vision OCR шага."""
```

Логика:
1. Если уже `.docx/.pdf/.odt/.rtf` — пропускаем конвертацию docx
2. `.doc` → LibreOffice headless (`--convert-to docx`) timeout=120 сек
3. При падении LibreOffice → catdoc fallback (текст, не docx)
4. Файлы < 1000 байт → пропускаем (скорее всего битый файл)

---

## Шаг 3: Фикс битых DOCX

**Файл:** `pipeline/docx_utils.py`

```python
def fix_broken_docx(path: str) -> bool:
    """Удаляет NULL image references в .rels файлах ZIP-архива docx."""
```

Боевая фича: часть файлов из OneDrive содержат `Target="../NULL"` в `.rels`,
из-за чего LibreOffice/Python-docx падают. Фиксируем in-place.

---

## Шаг 4: Извлечение текста

**Файл:** `pipeline/extractor.py`

```python
async def extract_text(content: bytes, filename: str) -> tuple[str, str]:
    """Возвращает (text, method). method: 'xml'|'pdf_text'|'vision_ocr'"""
```

Логика (waterfall):

```
.docx файл:
  → extract_text_from_docx_xml(content)    # прямой zipfile + re
  → если len(text) < 50 символов:
      → convert_docx_to_pdf(content)
      → extract_text_from_pdf(pdf_bytes)   # PyMuPDF fitz
      → если len(text) < 50:
          → vision_ocr(pdf_bytes)          # Qwen3-VL base64, до 10 страниц
          → если пустой → build_empty_result("документ пуст")

.pdf файл:
  → extract_text_from_pdf(pdf_bytes)       # PyMuPDF fitz
  → если len(text) < 100:
      → vision_ocr(pdf_bytes)

Порог для Vision OCR: MIN_TEXT_CHARS = 50 (docx) / 100 (pdf)
```

### Vision OCR (`pipeline/extractor.py`)

```python
async def vision_ocr(pdf_bytes: bytes, max_pages: int = 10) -> str:
    """PDF → страницы PNG (150 dpi) → base64 → Qwen3-VL-235B → текст"""
```

> ⚠️ Vision модель принимает **только base64**, не URL!
> Модель: `Qwen/Qwen3-VL-235B-A22B-Instruct`
> Ограничение: `vision_semaphore` (3 параллельных — дорого по токенам)

---

## Шаг 5: Определение языка и загрузка рубрики

**Файл:** `pipeline/rubric_loader.py`

```python
def get_rubric(text: str) -> tuple[str, str]:
    """Возвращает (rubric_content, lang). lang: 'ru'|'kk'"""
```

Логика:
1. `langdetect.detect(text[:500])` → `"kk"` или `"ru"`
2. При исключении → русская рубрика по умолчанию
3. Возвращает содержимое файла `rubrics/rubric_kaz.md` или `rubrics/rubric_rus.md`

---

## Шаг 6: Оценка через LLM

**Файл:** `pipeline/llm.py`

```python
async def evaluate_with_llm(rubric: str, student_work: str) -> tuple[str, dict]:
    """Возвращает (raw_response, usage). usage: {prompt_tokens, completion_tokens}"""
```

Параметры запроса:
```python
model = settings.nitec_model          # "openai/gpt-oss-120b"
temperature = 0.1
max_tokens = settings.nitec_max_tokens  # 4096
messages = [
    {"role": "system", "content": "Отвечай ТОЛЬКО валидным JSON без markdown."},
    {"role": "user",   "content": get_evaluation_prompt(rubric, student_work)}
]
```

> `openai/gpt-oss-120b` — reasoning модель. Пока думает, `content=None`.
> Используем `response.choices[0].message.content` после завершения (не streaming).
> Ограничение: `llm_semaphore` (5 параллельных, настраивается через `NITEC_MAX_WORKERS`)

---

## Шаг 7: Парсинг JSON ответа

**Файл:** `pipeline/llm.py`

```python
def parse_llm_response(raw: str) -> Optional[dict]:
    """Универсальный парсер: strip <think>, strip markdown, json.loads"""
```

Три попытки:
1. Strip `<think>.*</think>` (re.DOTALL) + `json.loads()`
2. Strip ` ```json ... ``` ` + `json.loads()`
3. `re.search(r'\{.*\}', text, re.DOTALL)` + `json.loads()`

Извлечение scores:
```python
def extract_scores(result: dict) -> tuple[dict, float, int]:
    """Возвращает (scores_dict, total_score, level)"""
    # scores_dict = {"s1_c1": 3, ..., "s5_c5": 1}  — 25 ключей
    # из result["full_report"]["sections"][N]["criteria"][M]["score"]
```

---

## Шаг 8: Сохранение результата

**Файл:** `tasks/evaluate.py`

```python
# Атомарное обновление счётчиков батча (без race condition)
await queries.increment_job_counter(job_id, success=(status == 'done'))

# Сохранение оценки
await queries.save_evaluation_result(eval_id, {
    "scores": scores,
    "total_score": total_score,
    "score_percentage": percentage,
    "score_level": level,
    "teacher_name": ...,
    "topic": ...,
    "feedback": ...,
    "llm_result": full_result_json,
    "report_path": report_path,
    "extraction_method": method,
    "doc_lang": lang,
    "prompt_tokens": usage["prompt_tokens"],
    "completion_tokens": usage["completion_tokens"],
    "processed_at": datetime.now(UTC),
    "status": "done",
})

# Проверка завершения батча
await check_job_completion(job_id)  # если все обработаны → job.status = 'done' + webhook
```

---

## Обработка невалидных документов

```python
def build_empty_result(reason: str) -> dict:
    """Структура результата для документов без содержания или с манипуляциями"""
    # scores = {"s1_c1": 0, ..., "s5_c5": 0}
    # total_score = 0, level = 1
    # feedback = reason
    # validation.is_valid = False
```

Причины (задаются в pipeline):
- `"Документ пуст или не содержит текста"` — < 50 символов после всех fallback
- `"Файл повреждён или обрезан при загрузке"` — corrupted ZIP header
- `"Файл не является документом"` — не docx/doc/pdf/odt/rtf

---

## Retry логика

Celery настройки в `tasks/evaluate.py`:
```python
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_file(self, eval_id: int):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc)
```

После 2 ретраев: `evaluation.status = 'failed'`.

Ручная переобработка: `POST /api/re-evaluate/{eval_id}` — сбрасывает счётчики и перезапускает.

---

## Webhook уведомление (при завершении батча)

```python
async def notify_webhook(job_id: int, webhook_url: str):
    payload = {
        "job_id": job_id,
        "status": "done",
        "total": job.total,
        "processed": job.processed,
        "failed": job.failed,
        "avg_score": ...,
    }
    await http_client.post(webhook_url, json=payload, timeout=10)
```

Вызывается в `check_job_completion` если `evaluation_job.webhook_url` задан.
