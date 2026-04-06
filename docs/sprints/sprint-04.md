# Sprint 4 — Results + Export + Dashboard

**Статус:** todo

## Цель

Таблица результатов в браузере, фильтры, экспорт Excel, технический мониторинг.

## Задачи

- [ ] `api/results.py` — `GET /results` (фильтры: job_id, city, trainer, group, status, level, пагинация)
- [ ] `GET /results/export` — Excel (колонки s1_c1…s5_c5 + мета)
- [ ] `api/dashboard.py` — `/monitor`, `/api/stats`, `/api/analytics`, `POST /api/re-evaluate/{id}`
- [ ] `templates/` — base, dashboard, upload, results, monitor
- [ ] `static/js/` — polling прогресса батча (если нужен AJAX)

## Проверка

Загрузка батча → прогресс на дашборде → фильтр по городу → скачать Excel.

## Следующий шаг

→ [sprint-05.md](sprint-05.md)
