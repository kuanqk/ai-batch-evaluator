# Авторизация

## Браузер

- `POST /accounts/login/` → session cookie → views с `@login_required`

## Staff

- Флаг `is_staff` — CRUD конфигураций (`/evaluators/…`), рубрик, системных настроек

## Django Admin

- `/admin/` — стандартная админка

## Глобальный DRF API (`/api/…`)

- **Django REST Framework:** `Authorization: Token <token>` или сессия
- Если в `.env` задан **`EVALUATOR_API_KEY`**, защищённые view дополнительно требуют:

```http
X-API-Key: <значение EVALUATOR_API_KEY>
```

Если ключ пустой — проверка отключена.

## Per-config API (`/api/ev/<slug>/…`)

- Заголовок **`X-API-Key`** должен совпадать с **`EvaluatorConfig.api_key`** для данного `slug`
- Конфиг **`is_active=True`**
- Аутентификация Django для этих маршрутов не используется

Подробнее по маршрутам: [../reference/api.md](../reference/api.md).
