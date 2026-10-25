# Дашборд трат: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Главный экран с тратами за сегодня, неделю и месяц, статусами свежести данных, графиком по категориям и последними транзакциями, с переключателем валюты. Отдельное React-SPA поверх API на django-ninja.

**Architecture:** Расчёты живут в пакете `money/dashboard/`: категории, периоды, курсы, траты, статусы. Это чистые функции поверх ORM, их легко тестировать. `money/api.py` даёт тонкие GET-эндпоинты на django-ninja с сессионной авторизацией. `frontend/` содержит Vite + React + TypeScript, типы API генерируются из OpenAPI. В проде Node есть только на этапе сборки Docker, а Caddy отдаёт статику SPA и проксирует Django-пути.

**Tech Stack:**
- бэкенд: Django 5.2, django-ninja 1.7.1 (Pydantic 2);
- фронт: React + TypeScript + Vite, Tailwind CSS v4 + shadcn/ui, TanStack Query, Recharts, openapi-typescript + openapi-fetch, Vitest + React Testing Library;
- Node 22.

**Spec:** `docs/superpowers/specs/2026-10-24-dashboard-design.md`

## Global Constraints

- Валюта по умолчанию: `AUD` (`DASHBOARD_DEFAULT_CURRENCY = 'AUD'`).
- Часовой пояс дашборда: `DASHBOARD_TIMEZONE = 'Australia/Brisbane'`. Неделя с понедельника по сегодня, месяц календарный с 1-го по сегодня.
- Пересчёт: `amount / rate(USD→валюта транзакции) × rate(USD→целевая)`. Курс берётся последний на дату транзакции или раньше, для USD rate = 1. `original_amount` не используется.
- Трата: `transaction_type='expense'` текущего пользователя, категория (и её предки) не помечена `is_spending=False`. Без категории тоже трата.
- Пороги свежести: ≤ 3 дней `ok`, 4–10 дней `warn`, > 10 дней `bad`. Активный счёт: есть транзакция за последние 180 дней. Зависшая выписка: PENDING дольше 1 часа. Курсы `bad`, если старше `STALE_RATE_AFTER` (уже есть в `money/models.py`, 7 дней).
- API первой версии только читает (GET), все эндпоинты требуют вход и отдают только данные `request.user`.
- Интерфейс только на русском.
- Node нужен только на этапе сборки. Новых долгоживущих сервисов на VM нет.
- Владелец впервые пишет на React. Код фронта должен быть обычным и идиоматичным, без самописных абстракций поверх библиотек.
- Существующие страницы `/money/...`, `/admin/`, `/accounts/` и внешнее API `/money/api/...` продолжают работать.

**Решения плана, уточняющие спецификацию:**
- Трата считается как `abs(amount)`, а не `-amount`. В данных есть расход с положительной суммой (комиссия FF `+30`), и он должен увеличивать траты, а не уменьшать.
- «Последние транзакции» показывают те же траты, что идут в суммы (без переводов, доходов и «не трат»), как на макете.
- Исходная сумма в списке показывается в валюте транзакции (`currency`). У BCC это валюта покупки, например ₸.
- «Без категории» на графике всегда идёт последней строкой.
- Подпись сравнения: «↑ 8% к сентябрю», где месяц в дательном падеже. Если в прошлом месяце трат не было, подпись не показывается.

## Review Focus

1. **Цикл в дереве категорий** (A → B → A, сохранённый через админку): подъём к корню и вычисление исключённых категорий не должны зависать. Тест: `test_category_cycle_does_not_hang` в задаче 1.
2. **Граница месяцев:** сегодня 31 марта, 15 января или 30 марта високосного года. «Прошлый месяц на ту же дату» должен давать 28 или 29 февраля и декабрь прошлого года, а не падать. Тест: `test_previous_month_to_date_clamps_and_wraps_year` в задаче 2.
3. **Сервер в UTC, а у владельца уже завтра:** в 15:00 UTC 23.10 в Брисбене уже 24.10, и «сегодня» должно быть 24.10. Тест: `test_dashboard_today_uses_brisbane_time` в задаче 2.
4. **Валюта из `localStorage` больше недоступна,** или в API пришла неизвестная валюта. Фронт откатывается на валюту по умолчанию, API отвечает 400. Тесты: `test_unknown_currency_is_rejected` в задаче 5 и «falls back to default currency» в задаче 6.
5. **Пустые данные:** новый пользователь или месяц без трат. Нули, пустые состояния, без деления на ноль в сравнении с прошлым месяцем. Тесты: `test_summary_for_user_without_transactions` в задаче 5 и `changePercent returns null when previous is zero` в задаче 7.

## Как запускать

- Бэкенд-тесты (dev-контейнер монтирует код в `/app`): `docker exec dj_money-web-1 python manage.py test money`
- Пересборка dev-контейнеров после смены `requirements.txt`: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build web celery_worker celery_beat`
- Фронт (на хосте, Node 22): `cd frontend && npm run check`, это проверка типов плюс тесты.

## Файлы

| Файл | Ответственность |
|---|---|
| `money/models.py` | + `ExpenseCategory.is_spending` |
| `money/migrations/0031_expensecategory_is_spending.py` | миграция поля |
| `money/admin.py` | флаг в списке и фильтре категорий |
| `money/testing.py` | фабрики для тестов дашборда и API (не тестовый модуль) |
| `money/dashboard/__init__.py` | пустой |
| `money/dashboard/categories.py` | `CategoryTree`: корни и исключённые категории |
| `money/dashboard/periods.py` | `Period`, «сегодня» и границы периодов |
| `money/dashboard/currency.py` | `RateBook`, `available_currencies` |
| `money/dashboard/spending.py` | выборка трат, суммы, по категориям, последние |
| `money/dashboard/status.py` | свежесть счетов, курсы, без категории, выписки |
| `money/schemas.py` | схемы ninja (ответы API) |
| `money/api.py` | `NinjaAPI` и эндпоинты |
| `money/test_dashboard.py` | тесты пакета `money/dashboard` |
| `money/test_api.py` | тесты API |
| `dj_money/settings.py` | `ninja` в приложениях, `DASHBOARD_*` |
| `dj_money/urls.py` | `/api/`, убрать редирект `/` → `/money/` |
| `requirements.txt` | `django-ninja==1.7.1` |
| `frontend/**` | SPA |
| `Dockerfile.prod`, `.dockerignore`, `docker-compose.gcp.yml`, `deploy/gcp/Caddyfile`, `entrypoint.prod.sh` | сборка и раздача SPA |
| `.gitignore` | `.superpowers/`, `frontend/node_modules/`, `!frontend/src/lib/` |

---

### Task 1: Флаг «не трата» и дерево категорий

Соответствует TSK-4 в Notion.

**Files:**
- Modify: `money/models.py` (`ExpenseCategory`)
- Create: `money/migrations/0031_expensecategory_is_spending.py` (через `makemigrations`)
- Modify: `money/admin.py` (`ExpenseCategoryAdmin`)
- Create: `money/testing.py`, `money/dashboard/__init__.py`, `money/dashboard/categories.py`
- Test: `money/test_dashboard.py`

**Interfaces:**
- Produces:
  - `ExpenseCategory.is_spending: BooleanField(default=True, help_text='Учитывать в тратах на дашборде')`
  - `money.testing`:
    - `create_user(username='u') -> User`
    - `create_currency(code: str) -> Currency`
    - `create_account(user, currency, name='Card') -> Account`
    - `create_category(user, name, parent=None, is_spending=True) -> ExpenseCategory`
    - `create_transaction(account, amount, on: date, *, transaction_type='expense', category=None, currency=None, place='', to_account=None) -> Transaction`
  - `money.dashboard.categories.CategoryTree(user)`:
    - `.root_of(category_id: int) -> ExpenseCategory`
    - `.excluded_ids() -> set[int]`

- [ ] **Step 1: Write the failing tests** in `money/test_dashboard.py`, class `CategoryTreeTests(TestCase)`:

```python
def test_children_of_not_spending_category_are_excluded(self):
    transfers = create_category(self.user, 'Переводы между своими', is_spending=False)
    child = create_category(self.user, 'Оплата карты', parent=transfers)
    create_category(self.user, 'Продукты')
    self.assertEqual(CategoryTree(self.user).excluded_ids(), {transfers.id, child.id})

def test_root_of_walks_up_to_top_level(self):
    food = create_category(self.user, 'Еда')
    cafe = create_category(self.user, 'Кафе', parent=food)
    coffee = create_category(self.user, 'Кофе', parent=cafe)
    self.assertEqual(CategoryTree(self.user).root_of(coffee.id), food)

def test_category_cycle_does_not_hang(self):
    a = create_category(self.user, 'A')
    b = create_category(self.user, 'B', parent=a)
    ExpenseCategory.objects.filter(pk=a.pk).update(parent_category=b)
    tree = CategoryTree(self.user)
    self.assertIn(tree.root_of(a.id), {a, b})
    self.assertEqual(tree.excluded_ids(), set())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec dj_money-web-1 python manage.py test money.test_dashboard`
Expected: ошибка импорта `money.testing` / `money.dashboard.categories`.

- [ ] **Step 3: Implement**
  - **Поле и миграция.** Добавить поле `is_spending` в модель и выполнить `docker exec dj_money-web-1 python manage.py makemigrations money -n expensecategory_is_spending`.
  - **Админка.** В `ExpenseCategoryAdmin`: `list_display = ('name', 'parent_category', 'is_spending', 'user')` и `list_filter = ('is_spending',)`.
  - **Фабрики `money/testing.py`.** `create_transaction` передаёт `original_amount=amount`, `original_currency=currency or account.currency` и `date_processing=on`. Так `Transaction.save` выставит курс 1 и не пойдёт искать `ExchangeRate`.
  - **`CategoryTree`.** Одним запросом грузит категории пользователя в словарь по `id`. Подъём к корню идёт по `parent_category_id` с множеством посещённых узлов: на цикле останавливается.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec dj_money-web-1 python manage.py test money`
Expected: все тесты, включая старые, проходят.

- [ ] **Step 5: Commit**

```bash
git add money/models.py money/migrations/0031_expensecategory_is_spending.py money/admin.py money/testing.py money/dashboard/ money/test_dashboard.py
git commit -m "Add is_spending flag to expense categories"
```

---

### Task 2: Периоды и пересчёт валют

Соответствует TSK-6.

**Files:**
- Create: `money/dashboard/periods.py`, `money/dashboard/currency.py`
- Modify: `dj_money/settings.py` (рядом с `TIME_ZONE`)
- Test: `money/test_dashboard.py`

**Interfaces:**
- Produces:
  - `settings.DASHBOARD_TIMEZONE = 'Australia/Brisbane'`, `settings.DASHBOARD_DEFAULT_CURRENCY = 'AUD'`
  - `periods`:
    - `@dataclass(frozen=True) class Period: start: date; end: date` (обе границы включительно)
    - `dashboard_today(now: datetime | None = None) -> date`
    - `week_to_date(today: date) -> Period`
    - `month_to_date(today: date) -> Period`
    - `previous_month_to_date(today: date) -> Period`
  - `currency`:
    - `RateBook(codes: Iterable[str], until: date)`
    - `.rate(code: str, on: date) -> Decimal | None`
    - `.convert(amount: Decimal, from_code: str, to_code: str, on: date) -> Decimal | None`
    - `available_currencies() -> list[str]`

- [ ] **Step 1: Write the failing tests:** классы `PeriodTests` и `RateBookTests`.

```python
def test_dashboard_today_uses_brisbane_time(self):
    now = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)
    self.assertEqual(dashboard_today(now), date(2026, 10, 24))

def test_week_starts_on_monday(self):
    self.assertEqual(week_to_date(date(2026, 10, 25)), Period(date(2026, 10, 19), date(2026, 10, 25)))
    self.assertEqual(week_to_date(date(2026, 10, 19)), Period(date(2026, 10, 19), date(2026, 10, 19)))

def test_month_to_date(self):
    self.assertEqual(month_to_date(date(2026, 10, 24)), Period(date(2026, 10, 1), date(2026, 10, 24)))

def test_previous_month_to_date_clamps_and_wraps_year(self):
    self.assertEqual(previous_month_to_date(date(2026, 3, 31)), Period(date(2026, 2, 1), date(2026, 2, 28)))
    self.assertEqual(previous_month_to_date(date(2024, 3, 30)), Period(date(2024, 2, 1), date(2024, 2, 29)))
    self.assertEqual(previous_month_to_date(date(2026, 1, 15)), Period(date(2025, 12, 1), date(2025, 12, 15)))
```

В `RateBookTests.setUp` заводятся USD, KZT, AUD и курсы USD→KZT `450` и USD→AUD `1.5` на 16.10.2026 (пятница).

```python
def test_cross_rate_uses_last_rate_on_or_before_date(self):
    book = RateBook(['KZT', 'AUD'], until=date(2026, 10, 18))
    self.assertEqual(book.convert(Decimal('-4500'), 'KZT', 'AUD', date(2026, 10, 18)), Decimal('-15'))

def test_usd_has_rate_one(self):
    book = RateBook(['AUD'], until=date(2026, 10, 18))
    self.assertEqual(book.convert(Decimal('10'), 'USD', 'AUD', date(2026, 10, 18)), Decimal('15'))
    self.assertEqual(book.convert(Decimal('15'), 'AUD', 'USD', date(2026, 10, 18)), Decimal('10'))

def test_same_currency_needs_no_rate(self):
    book = RateBook([], until=date(2026, 10, 18))
    self.assertEqual(book.convert(Decimal('7'), 'TRY', 'TRY', date(2020, 1, 1)), Decimal('7'))

def test_missing_rate_returns_none(self):
    book = RateBook(['KZT', 'AUD'], until=date(2026, 10, 18))
    self.assertIsNone(book.convert(Decimal('100'), 'KZT', 'AUD', date(2026, 10, 15)))

def test_available_currencies_are_usd_plus_quoted(self):
    self.assertEqual(available_currencies(), ['AUD', 'KZT', 'USD'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec dj_money-web-1 python manage.py test money.test_dashboard`
Expected: ошибки импорта `periods` / `currency`.

- [ ] **Step 3: Implement**
  - **`dashboard_today`.** Через `zoneinfo.ZoneInfo(settings.DASHBOARD_TIMEZONE)`, `now` по умолчанию `django.utils.timezone.now()`.
  - **`RateBook`.** Одним запросом грузит все `ExchangeRate` с `source_currency__code='USD'`, `target_currency__code__in=codes`, `date__lte=until`. Хранит их отсортированными по дате на код; `rate()` ищет через `bisect`. Результат `convert` не округляет.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec dj_money-web-1 python manage.py test money`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add money/dashboard/periods.py money/dashboard/currency.py dj_money/settings.py money/test_dashboard.py
git commit -m "Add dashboard periods and currency conversion"
```

---

### Task 3: Траты: суммы, категории, последние

Соответствует TSK-6 и TSK-7.

**Files:**
- Create: `money/dashboard/spending.py`
- Test: `money/test_dashboard.py`

**Interfaces:**
- Consumes: `CategoryTree` (задача 1), `Period`, `RateBook` (задача 2).
- Produces:
  - `spending_transactions(user: User, tree: CategoryTree) -> QuerySet[Transaction]`: только `expense` пользователя, без `tree.excluded_ids()`, `select_related('currency', 'category')`.
  - `spent(tx: Transaction, currency: str, book: RateBook) -> Decimal | None`: `abs(amount)` в целевой валюте; `None`, если `amount == 0` или нет курса.
  - `@dataclass class Total: amount: Decimal; unconverted: int`
  - `total_for(transactions: QuerySet[Transaction], period: Period, currency: str, book: RateBook) -> Total`
  - `UNCATEGORIZED = 'Без категории'`
  - `@dataclass class CategoryTotal: category_id: int | None; name: str; amount: Decimal`
  - `totals_by_category(transactions, period, currency, book, tree) -> list[CategoryTotal]`: корневые категории по убыванию суммы, «Без категории» последней (если есть). Непересчитанные пропускаются.
  - `recent(transactions: QuerySet[Transaction], today: date) -> list[Transaction]`: даты `today - 1 … today`, порядок `-date, -id`.

- [ ] **Step 1: Write the failing tests:** класс `SpendingTests`. В `setUp` заводятся AUD-счёт `self.account`, второй AUD-счёт `self.savings` (получатель перевода), `self.october = Period(date(2026, 10, 1), date(2026, 10, 31))` и `self.book = RateBook(['AUD'], until=date(2026, 10, 31))`. Хелперы: `self.spending()` возвращает `spending_transactions(self.user, CategoryTree(self.user))`, `self.total()` возвращает `total_for(self.spending(), self.october, 'AUD', self.book)`.

```python
def test_only_spending_expenses_are_counted(self):
    food = create_category(self.user, 'Продукты')
    transfers = create_category(self.user, 'Переводы между своими', is_spending=False)
    on = date(2026, 10, 20)
    create_transaction(self.account, Decimal('-100'), on, category=food)
    create_transaction(self.account, Decimal('-50'), on, category=create_category(self.user, 'Карта', parent=transfers))
    create_transaction(self.account, Decimal('500'), on, transaction_type='income')
    create_transaction(self.account, Decimal('-30'), on, transaction_type='transfer', to_account=self.savings)
    create_transaction(create_account(create_user('other'), self.aud), Decimal('-999'), on)
    self.assertEqual(self.total(), Total(amount=Decimal('100'), unconverted=0))

def test_positive_expense_counts_as_spending(self):
    create_transaction(self.account, Decimal('30'), date(2026, 10, 20))
    self.assertEqual(self.total().amount, Decimal('30'))

def test_unconverted_are_counted_not_summed(self):
    kzt_account = create_account(self.user, create_currency('KZT'), name='Kaspi')
    create_transaction(kzt_account, Decimal('-4500'), date(2026, 10, 20))  # нет курса USD→KZT
    create_transaction(self.account, Decimal('0'), date(2026, 10, 20))
    self.assertEqual(self.total(), Total(amount=Decimal('0'), unconverted=2))

def test_period_bounds_are_inclusive(self):
    for day in (date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 24), date(2026, 10, 25)):
        create_transaction(self.account, Decimal('-10'), day)
    total = total_for(self.spending(), Period(date(2026, 10, 1), date(2026, 10, 24)), 'AUD', self.book)
    self.assertEqual(total.amount, Decimal('20'))

def test_categories_roll_up_to_root_and_uncategorized_is_last(self):
    # Еда → Кафе -200, Еда -50, Транспорт -100, без категории -300
    names = [(c.name, c.amount) for c in totals_by_category(self.spending(), self.october, 'AUD', self.book, CategoryTree(self.user))]
    self.assertEqual(names, [('Еда', Decimal('250')), ('Транспорт', Decimal('100')), ('Без категории', Decimal('300'))])

def test_recent_is_today_and_yesterday(self):
    # траты 22, 23, 24 октября, today=24
    self.assertEqual([t.date for t in recent(self.spending(), date(2026, 10, 24))], [date(2026, 10, 24), date(2026, 10, 23)])
```

- [ ] **Step 2: Run to verify failure.** `docker exec dj_money-web-1 python manage.py test money.test_dashboard`, ожидается ImportError `spending`.
- [ ] **Step 3: Implement** функции из Interfaces в `money/dashboard/spending.py`.
- [ ] **Step 4: Run to verify pass.** `docker exec dj_money-web-1 python manage.py test money`, ожидается PASS.
- [ ] **Step 5: Commit**

```bash
git add money/dashboard/spending.py money/test_dashboard.py
git commit -m "Add dashboard spending calculations"
```

---

### Task 4: Статусы обновлений

Соответствует TSK-7.

**Files:**
- Create: `money/dashboard/status.py`
- Test: `money/test_dashboard.py`

**Interfaces:**
- Consumes: `Period` (задача 2), `spending_transactions` (задача 3), `STALE_RATE_AFTER` из `money.models`.
- Produces:
  - константы `FRESH_DAYS = 3`, `STALE_DAYS = 10`, `ACTIVE_ACCOUNT_DAYS = 180`, `PENDING_STUCK_AFTER = timedelta(hours=1)`
  - `Level = Literal['ok', 'warn', 'bad']`
  - `freshness_level(days: int) -> Level`
  - `@dataclass class AccountFreshness: name: str; last_date: date; days: int; level: Level`
  - `account_freshness(user: User, today: date) -> list[AccountFreshness]`: по счетам пользователя с любой транзакцией не старше 180 дней. Дата последней транзакции любого типа, сортировка по имени.
  - `@dataclass class RatesStatus: last_date: date | None; level: Level`
  - `rates_status(today: date) -> RatesStatus`: `ok`, если `today - last_date <= STALE_RATE_AFTER`, иначе (и при `None`) `bad`.
  - `uncategorized_count(transactions: QuerySet[Transaction], month: Period) -> int`
  - `@dataclass class FailedImport: source: str; uploaded_at: datetime`
  - `failed_imports(user: User) -> list[FailedImport]`: по каждому `BankSource` берётся последняя выписка пользователя, если она `FAILED`.
  - `stuck_pending_count(user: User, now: datetime) -> int`

- [ ] **Step 1: Write the failing tests:** класс `StatusTests`.

```python
def test_freshness_thresholds(self):
    self.assertEqual([freshness_level(d) for d in (0, 3, 4, 10, 11)], ['ok', 'ok', 'warn', 'warn', 'bad'])

def test_inactive_accounts_are_hidden_and_manual_ones_shown(self):
    # счёт ANZ AUD: одна транзакция без выписки 5 дней назад; счёт Halyk KZT: транзакция 200 дней назад
    self.assertEqual([(a.name, a.days, a.level) for a in account_freshness(self.user, self.today)], [('ANZ AUD', 5, 'warn')])

def test_rates_older_than_a_week_are_bad(self):
    # последний курс 7 дней назад → 'ok'; 8 дней назад → 'bad'; курсов нет → RatesStatus(None, 'bad')
    ...

def test_only_latest_failed_import_per_source_is_reported(self):
    # BCC: FAILED, потом COMPLETED → не показывается; CommBank: COMPLETED, потом FAILED → показывается
    self.assertEqual([f.source for f in failed_imports(self.user)], ['CommBank'])

def test_pending_older_than_an_hour_is_stuck(self):
    # uploaded_at ставится через .update(): 2 часа назад → считается, 10 минут назад → нет
    self.assertEqual(stuck_pending_count(self.user, self.now), 1)
```

- [ ] **Step 2: Run to verify failure.** Та же команда, ожидается ImportError `status`.
- [ ] **Step 3: Implement** функции из Interfaces в `money/dashboard/status.py`. Пороги берутся только из констант модуля.
- [ ] **Step 4: Run to verify pass.** `docker exec dj_money-web-1 python manage.py test money`, ожидается PASS.
- [ ] **Step 5: Commit**

```bash
git add money/dashboard/status.py money/test_dashboard.py
git commit -m "Add dashboard data freshness status"
```

---

### Task 5: API на django-ninja

Соответствует TSK-5 и TSK-7.

**Files:**
- Modify: `requirements.txt` (`django-ninja==1.7.1`), `dj_money/settings.py` (`'ninja'` в `INSTALLED_APPS`), `dj_money/urls.py` (`path('api/', api.urls)`)
- Create: `money/schemas.py`, `money/api.py`, `frontend/openapi.json` (экспорт схемы)
- Test: `money/test_api.py`

**Interfaces:**
- Consumes: всё из задач 1–4.
- Produces (HTTP, используется фронтом через сгенерированные типы):
  - `api = NinjaAPI(title='dj_money', auth=django_auth, docs_decorator=staff_member_required, urls_namespace='api')` в `money/api.py`
  - `GET /api/me` → `MeOut { username: str, default_currency: str, currencies: list[str] }`
  - `GET /api/dashboard/summary?currency=` → `SummaryOut { currency: str, as_of: date, today: float, week: float, month: float, previous_month_to_date: float, unconverted: int }`
  - `GET /api/dashboard/categories?currency=&period=week|month` → `CategoriesOut { currency: str, period: str, start: date, end: date, items: list[CategoryOut { id: int | None, name: str, amount: float }] }`
  - `GET /api/dashboard/transactions/recent?currency=` → `RecentOut { currency: str, items: list[RecentTransactionOut { id: int, date: date, title: str, category: str | None, amount: float | None, original_amount: float, original_currency: str }] }`. `title` берётся из `place`, иначе из `comment`; `category` хранит собственное имя категории; `amount` — пересчитанная положительная трата.
  - `GET /api/dashboard/status` → `StatusOut { accounts: list[AccountStatusOut { name, last_date, days, level }], rates: RatesOut { last_date: date | None, level }, uncategorized: UncategorizedOut { count: int, level }, failed_imports: list[FailedImportOut { source, uploaded_at }], stuck_pending: int }`. `uncategorized.level` равен `warn`, если `count > 0`, иначе `ok`.
  - Все суммы — `float`, округлённые до 2 знаков (`round(float(x), 2)`): так в TypeScript они получаются числами, а не строками. Параметр `currency` по умолчанию равен `settings.DASHBOARD_DEFAULT_CURRENCY`; если валюты нет в `available_currencies()`, ответ `HttpError(400, 'Неизвестная валюта')`.

- [ ] **Step 1: Install django-ninja.** Добавить строку в `requirements.txt` и пересобрать dev-контейнеры командой из раздела «Как запускать». Проверка: `docker exec dj_money-web-1 python -c "import ninja; print(ninja.__version__)"` выводит `1.7.1`.

- [ ] **Step 2: Write the failing tests:** класс `DashboardApiTests` с `self.client.force_login(self.user)` в `setUp`. «Сегодня» фиксируется через `mock.patch('money.api.dashboard_today', return_value=...)`.

```python
def test_endpoints_require_login(self):
    self.client.logout()
    for url in ['/api/me', '/api/dashboard/summary', '/api/dashboard/categories', '/api/dashboard/transactions/recent', '/api/dashboard/status']:
        self.assertEqual(self.client.get(url).status_code, 401, url)

def test_me_returns_default_currency(self):
    self.assertEqual(self.client.get('/api/me').json(), {'username': 'u', 'default_currency': 'AUD', 'currencies': ['AUD', 'KZT', 'USD']})

def test_summary_for_user_without_transactions(self):
    body = self.client.get('/api/dashboard/summary').json()
    self.assertEqual((body['today'], body['month'], body['previous_month_to_date'], body['unconverted']), (0, 0, 0, 0))

def test_summary_converts_to_requested_currency(self):
    # трата -4500 KZT сегодня, курсы USD→KZT 450 и USD→AUD 1.5
    self.assertEqual(self.client.get('/api/dashboard/summary?currency=AUD').json()['today'], 15.0)
    self.assertEqual(self.client.get('/api/dashboard/summary?currency=KZT').json()['today'], 4500.0)

def test_unknown_currency_is_rejected(self):
    self.assertEqual(self.client.get('/api/dashboard/summary?currency=XXX').status_code, 400)

def test_other_users_data_is_not_returned(self):
    # трата другого пользователя сегодня → summary.today == 0 и recent.items == []
    ...

def test_openapi_schema_is_exported(self):
    out = StringIO()
    call_command('export_openapi_schema', api='money.api.api', indent=2, stdout=out)
    committed = json.loads((settings.BASE_DIR / 'frontend' / 'openapi.json').read_text())
    self.assertEqual(json.loads(out.getvalue()), committed, 'Run export_openapi_schema and npm run gen:api')
```

- [ ] **Step 3: Run to verify failure.** `docker exec dj_money-web-1 python manage.py test money.test_api`, ожидается 404 / ImportError.

- [ ] **Step 4: Implement**
  - `money/schemas.py` и `money/api.py` по Interfaces.
  - `money/api.py` импортирует `from money.dashboard.periods import dashboard_today` (тесты мокают `money.api.dashboard_today`).
  - Каждый эндпоинт берёт `today = dashboard_today()`, строит `CategoryTree` и `RateBook(available_currencies(), until=today)` и зовёт функции из `money/dashboard/`. Своих расчётов в эндпоинтах нет. `uncategorized` в status считается за `month_to_date(today)`.
  - Подключить `api.urls` в `dj_money/urls.py`.

- [ ] **Step 5: Export the schema**

Run: `docker exec dj_money-web-1 python manage.py export_openapi_schema --api money.api.api --indent 2 --output frontend/openapi.json`
Expected: файл создан (каталог проекта смонтирован в контейнер как `/app`).

- [ ] **Step 6: Run to verify pass.** `docker exec dj_money-web-1 python manage.py test money`, ожидается PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt dj_money/settings.py dj_money/urls.py money/schemas.py money/api.py money/test_api.py frontend/openapi.json
git commit -m "Add read-only dashboard API on django-ninja"
```

---

### Task 6: Каркас фронтенда

Соответствует TSK-8.

**Files:**
- Create: `frontend/`, созданный командой `npm create vite@latest frontend -- --template react-ts` (в корне репозитория). Уже лежащий там `openapi.json` сохранить.
- Modify: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.app.json`, `frontend/src/index.css`, `frontend/src/main.tsx`, `frontend/src/App.tsx`
- Create:
  - `frontend/src/api/schema.d.ts` (генерируется);
  - `frontend/src/api/client.ts`, `frontend/src/api/queries.ts`;
  - `frontend/src/hooks/useCurrency.ts`;
  - `frontend/src/components/CurrencySwitcher.tsx`;
  - `frontend/src/test/setup.ts`;
  - `frontend/README.md`.
- Modify: `.gitignore`
- Test: `frontend/src/hooks/useCurrency.test.ts`, `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: `frontend/openapi.json` (задача 5).
- Produces:
  - scripts в `package.json`:
    - `dev`, `build` (`tsc -b && vite build`);
    - `test` (`vitest run`);
    - `check` (`tsc -b && vitest run`);
    - `gen:api` (`openapi-typescript openapi.json -o src/api/schema.d.ts`).
  - alias `@` → `src` (нужен shadcn/ui).
  - `client.ts`:
    - `export const api = createClient<paths>({ baseUrl: '' })` (openapi-fetch) с middleware: ответ 401 → `redirectToLogin()`;
    - `redirectToLogin(): void` → `window.location.assign('/accounts/login/?next=/')`, в отдельном модуле `frontend/src/api/redirect.ts`, чтобы его можно было мокать.
  - `queries.ts`:
    - `useMe()`, `useSummary(currency: string)`, `useCategories(currency: string, period: 'week' | 'month')`, `useRecent(currency: string)`, `useStatus()`;
    - каждый — `useQuery` с ключом `['<name>', ...параметры]`, при ошибке API бросает исключение.
  - `useCurrency.ts`: `useCurrency(me: MeOut | undefined): [string, (code: string) => void]`. Читает и пишет `localStorage['dj_money.currency']` в `try/catch`; если сохранённой валюты нет в `me.currencies`, берёт `me.default_currency`.
  - `CurrencySwitcher({ value, options, onChange })` на shadcn `Select`.

- [ ] **Step 1: Scaffold and install**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query recharts openapi-fetch
npm install -D tailwindcss @tailwindcss/vite openapi-typescript vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @types/node
npx shadcn@latest init
npx shadcn@latest add card button select toggle-group badge skeleton alert
npm run gen:api
```

- **`vite.config.ts`:** плагины `react()` и `tailwindcss()`.
- **Прокси:** `server.proxy` для `/api`, `/accounts`, `/admin`, `/static` → `http://localhost:8000` **без** `changeOrigin`. Тогда Host остаётся `localhost:5173` и совпадает с Origin, и CSRF-проверка формы входа Django проходит.
- **Тесты:** `test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' }`.
- **`.gitignore`:** добавить `.superpowers/`, `frontend/node_modules/` и `!frontend/src/lib/` (глобальный шаблон `lib/` иначе спрячет `src/lib/utils.ts` от shadcn).

- [ ] **Step 2: Write the failing tests**

```ts
// useCurrency.test.ts
it('falls back to default currency when stored one is no longer available', () => {
  localStorage.setItem('dj_money.currency', 'TRY')
  const { result } = renderHook(() => useCurrency({ username: 'u', default_currency: 'AUD', currencies: ['AUD', 'KZT', 'USD'] }))
  expect(result.current[0]).toBe('AUD')
})
it('remembers the chosen currency', () => {
  // act(() => setCurrency('KZT')) → значение 'KZT' и localStorage['dj_money.currency'] === 'KZT'
})

// client.test.ts
vi.mock('./redirect', () => ({ redirectToLogin: vi.fn() }))
it('redirects to Django login on 401', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))
  await api.GET('/api/me')
  expect(redirectToLogin).toHaveBeenCalled()
})
```

- [ ] **Step 3: Run to verify failure.** `cd frontend && npm test`, ожидается ошибка импорта `useCurrency` / `client`.

- [ ] **Step 4: Implement**
  - `redirect.ts`, `client.ts`, `queries.ts`, `useCurrency.ts`, `CurrencySwitcher.tsx` по Interfaces.
  - `main.tsx` оборачивает `<App />` в `QueryClientProvider`.
  - `App.tsx` пока показывает шапку «DJ Money», имя пользователя и `CurrencySwitcher`.
  - `README.md`: запуск бэкенда, `npm run dev`, экспорт схемы командой из задачи 5 и `npm run gen:api`.

- [ ] **Step 5: Run to verify pass**

Run: `cd frontend && npm run check && npm run build`
Expected: типы без ошибок, тесты PASS, `dist/` собран.

- [ ] **Step 6: Commit**

```bash
git add .gitignore frontend
git commit -m "Scaffold React frontend with typed API client"
```

---

### Task 7: Главный экран (вариант A)

Соответствует TSK-9.

**Files:**
- Create:
  - `frontend/src/lib/format.ts`;
  - `frontend/src/components/dashboard/SummaryCards.tsx`, `StatusChips.tsx`, `CategoryChart.tsx`, `RecentTransactions.tsx`, `Dashboard.tsx`.
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/lib/format.test.ts`, `frontend/src/components/dashboard/Dashboard.test.tsx`

**Interfaces:**
- Consumes: хуки из `queries.ts` и `useCurrency`, `CurrencySwitcher` (задача 6). Схемы ответов из задачи 5.
- Produces (`format.ts`):
  - `formatMoney(amount: number, currency: string, fractionDigits: 0 | 2): string` — `Intl.NumberFormat('ru-RU', { style: 'currency', currency, ... })`;
  - `changePercent(current: number, previous: number): number | null` — `null`, если `previous === 0`, иначе округлённые проценты;
  - `monthDative(monthIndex: number): string` — 0 → «январю» … 11 → «декабрю»;
  - `levelClass(level: 'ok' | 'warn' | 'bad'): string` — классы Tailwind: зелёный, янтарный, красный.

Раскладка как в макете A (`.superpowers/brainstorm/*/content/layout.html`):
- **Шапка:** переключатель валюты.
- **Суммы:** три карточки «Сегодня» / «Эта неделя» / название текущего месяца («Октябрь»). Суммы целыми; под месяцем подпись «↑ 8% к сентябрю» или «↓ …».
- **Статусы:** строка меток-чипов: счета `«{name} · {days} дн.»`, «Курсы», «Без категории · N», FAILED-выписки, зависшие выписки.
- **Предупреждение:** `Alert` «N транзакций без курса не вошли в суммы», если `unconverted > 0`.
- **Нижний блок:** две колонки на `md+`, одна на телефоне:
  - слева график Recharts, горизонтальные полосы с `ToggleGroup` «Неделя / Месяц» (по умолчанию месяц), «Без категории» серым;
  - справа последние траты, сгруппированные «Сегодня» / «Вчера», суммы с двумя знаками и исходная сумма мелко.
- **Состояния:** у каждого блока свой `Skeleton` при загрузке и своё сообщение об ошибке, пустые состояния («Трат за этот период нет»).

- [ ] **Step 1: Write the failing tests**

```ts
// format.test.ts
it('formats cards without and lists with cents', () => {
  expect(formatMoney(2480.4, 'AUD', 0)).toMatch(/2\s?480/)
  expect(formatMoney(31.5, 'AUD', 2)).toMatch(/31,50/)
})
it('changePercent returns null when previous is zero', () => {
  expect(changePercent(100, 0)).toBeNull()
  expect(changePercent(108, 100)).toBe(8)
})
it('monthDative', () => { expect(monthDative(8)).toBe('сентябрю') })
it('levelClass gives a distinct color per level', () => {
  const classes = (['ok', 'warn', 'bad'] as const).map(levelClass)
  expect(new Set(classes).size).toBe(3)
})

// Dashboard.test.tsx — fetch подменён фикстурами для всех пяти эндпоинтов
it('renders all blocks', async () => {
  render(<Dashboard />, { wrapper: QueryWrapper })
  expect(await screen.findByText('Сегодня')).toBeInTheDocument()
  expect(screen.getByText(/CommBank AUD/)).toBeInTheDocument()
  expect(screen.getByText('Без категории')).toBeInTheDocument()
  expect(screen.getByText('Woolworths')).toBeInTheDocument()
})
it('refetches in the chosen currency', async () => {
  // выбрать KZT в CurrencySwitcher → fetch вызван с URL, содержащими 'currency=KZT', для summary, categories и recent
})
it('shows unconverted warning', async () => {
  // summary.unconverted = 3 → виден текст про 3 транзакции без курса
})
```

- [ ] **Step 2: Run to verify failure.** `cd frontend && npm test`, ожидается ошибка импорта.
- [ ] **Step 3: Implement** `format.ts` и компоненты. `App.tsx` рендерит `Dashboard`.
- [ ] **Step 4: Run to verify pass.** `cd frontend && npm run check`, ожидается PASS.
- [ ] **Step 5: Manual check.** При запущенном dev-бэкенде `npm run dev` → `http://localhost:5173/`. Без входа должен быть редирект на логин Django, после входа виден дашборд. Переключение валюты меняет суммы, ширина 375px даёт одну колонку.
- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "Build dashboard home screen"
```

---

### Task 8: Сборка и раздача в проде

Соответствует TSK-10.

**Files:**
- Modify: `Dockerfile.prod`, `.dockerignore`, `docker-compose.gcp.yml`, `deploy/gcp/Caddyfile`, `entrypoint.prod.sh`, `dj_money/urls.py`
- Test: `money/test_api.py`

**Interfaces:**
- Consumes: `npm run check` и `npm run build` (задача 6).
- Produces: образ, в котором `/home/app/web/frontend_dist` содержит собранное SPA; volume `frontend`; Caddy отдаёт SPA с `/`.

- [ ] **Step 1: Write the failing test**

```python
def test_root_is_served_by_frontend_not_django(self):
    self.assertEqual(self.client.get('/').status_code, 404)
    self.assertEqual(self.client.get('/money/').status_code, 200)
```

- [ ] **Step 2: Run to verify failure.** `docker exec dj_money-web-1 python manage.py test money.test_api`, ожидается 301 вместо 404.

- [ ] **Step 3: Implement**
  - **`dj_money/urls.py`:** убрать `RedirectView` для `''`.
  - **`Dockerfile.prod`:** новая стадия `FROM node:22-alpine AS frontend` (`WORKDIR /frontend`, `COPY frontend/package*.json ./`, `npm ci`, `COPY frontend/ ./`, `npm run check && npm run build`). В финальной стадии после `COPY . $APP_HOME` добавить `COPY --from=frontend /frontend/dist $APP_HOME/frontend_dist`.
  - **`.dockerignore`:** добавить `frontend/node_modules` и `frontend/dist`.
  - **`entrypoint.prod.sh`:** создавать и `chown` также `/home/app/web/frontend_public`.
  - **`docker-compose.gcp.yml`:**
    - у `web` команда начинается с `rm -rf frontend_public/* && cp -r frontend_dist/. frontend_public/ && python manage.py collectstatic ...`;
    - volume `frontend:/home/app/web/frontend_public` у `web`, `frontend:/srv/frontend:ro` у `caddy`;
    - `frontend:` в списке volumes.
  - **`deploy/gcp/Caddyfile`:**

```
{$DOMAIN} {
	encode gzip

	handle_path /static/* {
		root * /srv/static
		file_server
	}

	@django path /api/* /admin/* /accounts/* /money/*
	handle @django {
		reverse_proxy web:8000
	}

	handle {
		root * /srv/frontend
		try_files {path} /index.html
		file_server
	}
}
```

- [ ] **Step 4: Verify**

Run: `docker exec dj_money-web-1 python manage.py test money`
Expected: PASS.

Run: `docker build -f Dockerfile.prod -t dj_money:spa-check .`
Expected: сборка успешна, в логе видно, что `npm run check` прошёл.

Run: `docker run --rm -e DOMAIN=localhost -v "$PWD/deploy/gcp/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2.11.6-alpine caddy validate --config /etc/caddy/Caddyfile`
Expected: `Valid configuration`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile.prod .dockerignore docker-compose.gcp.yml deploy/gcp/Caddyfile entrypoint.prod.sh dj_money/urls.py money/test_api.py
git commit -m "Serve the frontend from Caddy in the GCP deployment"
```

- [ ] **Step 6: После деплоя (владелец).**
  - Миграция 0031 применится сама: `deploy/gcp/deploy.sh` уже выполняет `migrate`.
  - Открыть `https://$DOMAIN/`, войти и увидеть дашборд.
  - В админке создать категорию «Переводы между своими» со снятым флагом (TSK-11).
