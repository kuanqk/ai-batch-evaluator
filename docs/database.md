# База данных

Django ORM + PostgreSQL. Миграции в `apps/accounts/migrations/` и `apps/batch/migrations/`.

## Модели

### `accounts.CustomUser` (extends AbstractUser)

Стандартный Django user. Можно расширять полями.

### `batch.EvaluationJob`

| Поле | Тип | Описание |
|------|-----|---------|
| id | BigInt PK | авто |
| name | CharField(255) | название задания |
| source_file | CharField(255) | имя загруженного файла |
| total | Int | всего записей |
| processed | Int | успешно оценено (атомарный F('processed')+1) |
| failed | Int | ошибочных |
| paused | Bool | флаг паузы |
| status | CharField | pending / running / done / failed |
| webhook_url | URLField | POST при завершении |
| created_by | FK → CustomUser | кто создал |
| created_at / updated_at | DateTimeField | авто |

### `batch.Evaluation`

| Поле | Тип | Описание |
|------|-----|---------|
| id | BigInt PK | авто |
| job | FK → EvaluationJob | NULL для single |
| material_id | Int | внешний ID (для Beles) |
| file_path | Text | путь из CSV |
| file_url | Text | URL для скачивания |
| city / trainer / group_name / file_name | Char | метаданные |
| teacher_name / topic | Text | из LLM-ответа |
| scores | JSONField | {s1_c1: 3, …, s5_c5: 2} |
| total_score | Float | сумма баллов (макс 75) |
| score_percentage | Float | % от 75 |
| score_level | Int | 1-4 |
| feedback | Text | краткий вывод |
| llm_result | JSONField | полный ответ LLM |
| status | Char | pending/processing/done/failed |
| current_step | Int | 0-8 |
| error | Text | текст ошибки |
| extraction_method | Char | xml/pdf_text/vision_ocr/plain |
| doc_lang | Char | ru/kk |
| file_size_bytes / doc_chars | Int | метрики |
| prompt_tokens / completion_tokens | Int | токены LLM |
| started_at / processed_at | DateTime | временны́е метки |

## Атомарные обновления

```python
# Правильно — без race condition
EvaluationJob.objects.filter(pk=job_id).update(processed=F('processed') + 1)

# Неправильно
job = EvaluationJob.objects.get(pk=job_id)
job.processed += 1
job.save()
```

## Финализация задания

```python
with transaction.atomic():
    job = EvaluationJob.objects.select_for_update().get(pk=job_id)
    if job.processed + job.failed >= job.total:
        EvaluationJob.objects.filter(pk=job_id).update(status='done')
```
