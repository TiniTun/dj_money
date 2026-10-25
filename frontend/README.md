# DJ Money: фронтенд

SPA на React + TypeScript + Vite. Стили: Tailwind CSS и shadcn/ui. Данные: TanStack Query и типизированный клиент `openapi-fetch`. Node нужен только для разработки и сборки.

## Запуск для разработки

1. Запустить бэкенд (Django на `http://localhost:8000`), например через Docker:

   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
   ```

2. В другом терминале:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Открыть `http://localhost:5173`. Vite проксирует `/api`, `/accounts`, `/admin` и `/static` на Django. Прокси работает без `changeOrigin`, чтобы заголовок Host остался `localhost:5173`: иначе проверка CSRF на форме входа не пройдёт. Если вы не вошли, любой запрос к API вернёт 401, и приложение перенаправит на страницу входа Django.

## Скрипты

| Команда           | Что делает                                              |
| ----------------- | ------------------------------------------------------- |
| `npm run dev`     | dev-сервер Vite                                         |
| `npm run build`   | проверка типов и сборка в `dist/`                       |
| `npm test`        | тесты (Vitest)                                          |
| `npm run check`   | проверка типов и тесты                                  |
| `npm run gen:api` | типы API из `openapi.json` в `src/api/schema.d.ts`      |

## Типы API

Схема API хранится в `openapi.json`, типы для TypeScript генерируются из неё. После изменения API на бэкенде:

```bash
# из корня репозитория: экспорт схемы
docker exec dj_money-web-1 python manage.py export_openapi_schema --api money.api.api --indent 2 --output frontend/openapi.json

# из frontend/: обновление типов
npm run gen:api
```

Обе команды дают файлы, которые коммитятся. Бэкенд-тест проверяет, что `openapi.json` совпадает с живой схемой.

## Структура

- `src/api/`: клиент (`client.ts`), хуки запросов (`queries.ts`), сгенерированные типы (`schema.d.ts`).
- `src/hooks/`: `useCurrency`, выбор валюты с запоминанием в `localStorage`.
- `src/components/`: компоненты приложения; `src/components/ui/` создан shadcn/ui.
- `src/lib/utils.ts`: вспомогательная функция `cn` от shadcn/ui.
