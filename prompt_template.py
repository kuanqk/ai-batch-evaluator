"""LLM prompt for lesson-plan evaluation (JSON output)."""


def get_evaluation_prompt(rubric: str, student_work: str) -> str:
    return f"""Ты — эксперт по оценке учебных планов. Ниже дана рубрика и текст работы педагога.

## Рубрика оценивания
{rubric}

## Текст плана урока (работа педагога)
{student_work}

## Инструкция
Оцени работу строго по рубрике. Верни ОДИН JSON-объект без markdown и без пояснений вне JSON.

Схема ответа (все поля обязательны, кроме null):
- validation: is_valid (bool), is_substantive (bool), is_on_topic (bool), failure_reason (string|null)
- teacher_name: строка (ФИО из текста или "Не указано")
- topic: строка (тема урока)
- full_report:
  - overall_score: total_points (0-75), max_points 75, percentage (float), level (1-4)
  - sections: массив из 5 элементов; у каждого section_number 1..5, section_title, criteria — ровно 5 критериев с criterion_number 1..5, score 0-3, evidence_quote, justification, recommendation
  - top_strengths: массив строк
  - critical_gaps: массив строк
- brief_report_json: sections с краткими итогами по разделам, overall_recommendation
- level_assessment: level 1-4, description, justification

Ключи для критериев в логике: раздел S (1-5), критерий C (1-5) → идентификатор s{{S}}_c{{C}}. В full_report.sections должно быть 5 разделов × 5 критериев = 25 оценок score.

Отвечай ТОЛЬКО валидным JSON."""
