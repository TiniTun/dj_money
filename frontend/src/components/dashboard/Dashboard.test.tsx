import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement, ReactNode } from 'react'
import { cloneElement } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Dashboard } from './Dashboard'

// ResponsiveContainer measures its parent, and jsdom has no layout, so the
// chart would render nothing. In tests we give the chart a fixed size instead.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) =>
      cloneElement(children, { width: 600, height: 300 }),
  }
})

function QueryWrapper({ children }: { children: ReactNode }) {
  // A fresh client per render, so tests do not share cached data.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

type Fixtures = {
  summaryUnconverted?: number
  categories?: { id: number | null; name: string; amount: number }[]
  summaryStatus?: number
  accounts?: { name: string; last_date: string; days: number; level: 'ok' | 'warn' | 'bad' }[]
  failedImports?: { source: string; uploaded_at: string }[]
  stuckPending?: number
}

// Replaces fetch with fixtures for all five endpoints and returns the mock,
// so that tests can look at the URLs that were requested.
function mockApi({
  summaryUnconverted = 0,
  categories,
  summaryStatus = 200,
  accounts,
  failedImports = [],
  stuckPending = 0,
}: Fixtures = {}) {
  const fetchMock = vi.fn(async (request: Request) => {
    const url = new URL(request.url)
    const currency = url.searchParams.get('currency')
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

    switch (url.pathname) {
      case '/api/me':
        return json({ username: 'egor', default_currency: 'AUD', currencies: ['AUD', 'KZT', 'USD'] })
      case '/api/dashboard/summary':
        if (summaryStatus !== 200) return json({}, summaryStatus)
        return json({
          currency,
          as_of: '2026-10-24',
          today: 42.2,
          week: 612,
          month: 2480.4,
          previous_month_to_date: 2296,
          unconverted: summaryUnconverted,
        })
      case '/api/dashboard/categories':
        return json({
          currency,
          period: url.searchParams.get('period'),
          start: '2026-10-01',
          end: '2026-10-24',
          items: categories ?? [
            { id: 1, name: 'Продукты', amount: 720 },
            { id: 2, name: 'Жильё', amount: 600 },
            { id: null, name: 'Без категории', amount: 280 },
          ],
        })
      case '/api/dashboard/transactions/recent':
        return json({
          currency,
          items: [
            {
              id: 1,
              date: '2026-10-24',
              title: 'Woolworths',
              category: 'Продукты',
              amount: 31.5,
              original_amount: 31.5,
              original_currency: 'AUD',
            },
            {
              id: 2,
              date: '2026-10-23',
              title: 'MAGNUM ALMATY',
              category: null,
              amount: 22.4,
              original_amount: 8400,
              original_currency: 'KZT',
            },
          ],
        })
      case '/api/dashboard/status':
        return json({
          accounts: accounts ?? [{ name: 'CommBank AUD', last_date: '2026-10-22', days: 2, level: 'ok' }],
          rates: { last_date: '2026-10-24', level: 'ok' },
          uncategorized: { count: 14, level: 'warn' },
          failed_imports: failedImports,
          stuck_pending: stuckPending,
        })
      default:
        return json({}, 404)
    }
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function requestedUrls(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.map(([request]) => request.url)
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

it('renders all blocks', async () => {
  mockApi()
  render(<Dashboard />, { wrapper: QueryWrapper })

  // "Сегодня" is both a card title and a group title in the recent list.
  expect((await screen.findAllByText('Сегодня')).length).toBeGreaterThan(0)
  expect(await screen.findByText(/CommBank AUD/)).toBeInTheDocument()
  expect(await screen.findByText('Без категории')).toBeInTheDocument()
  expect(await screen.findByText('Woolworths')).toBeInTheDocument()
  // Month card: title, amount without cents, comparison with the previous month.
  expect(await screen.findByText('Октябрь')).toBeInTheDocument()
  expect(await screen.findByText(/2\s?480/)).toBeInTheDocument()
  expect(await screen.findByText('↑ 8% к сентябрю')).toBeInTheDocument()
  // The original amount of a converted transaction is shown next to the converted one.
  expect(await screen.findByText(/8\s?400/)).toBeInTheDocument()
})

it('refetches in the chosen currency', async () => {
  const fetchMock = mockApi()
  const user = userEvent.setup()
  render(<Dashboard />, { wrapper: QueryWrapper })

  await user.click(await screen.findByRole('combobox', { name: 'Валюта' }))
  await user.click(await screen.findByRole('option', { name: 'KZT' }))

  await waitFor(() => {
    const urls = requestedUrls(fetchMock)
    for (const path of ['summary', 'categories', 'transactions/recent']) {
      expect(urls.some((url) => url.includes(`/api/dashboard/${path}`) && url.includes('currency=KZT'))).toBe(true)
    }
  })
})

it('does not request anything in a currency before /api/me resolves', async () => {
  const fetchMock = mockApi()
  render(<Dashboard />, { wrapper: QueryWrapper })

  // Right after the first render only /api/me (and the currency-free status) may be requested.
  const early = requestedUrls(fetchMock).filter((url) => url.includes('currency='))
  expect(early).toEqual([])
  await screen.findByText('Woolworths')
})

it('reloads categories when switching to the week', async () => {
  const fetchMock = mockApi()
  const user = userEvent.setup()
  render(<Dashboard />, { wrapper: QueryWrapper })

  await screen.findByText('Продукты', { selector: 'tspan, text' })
  expect(requestedUrls(fetchMock).some((url) => url.includes('period=month'))).toBe(true)

  await user.click(screen.getByRole('radio', { name: 'Неделя' }))
  await waitFor(() => {
    expect(requestedUrls(fetchMock).some((url) => url.includes('period=week'))).toBe(true)
  })
})

it('shows unconverted warning', async () => {
  mockApi({ summaryUnconverted: 3 })
  render(<Dashboard />, { wrapper: QueryWrapper })

  expect(await screen.findByText(/3 транзакции без курса не вошли в суммы/)).toBeInTheDocument()
})

it('does not show the warning when everything is converted', async () => {
  mockApi({ summaryUnconverted: 0 })
  render(<Dashboard />, { wrapper: QueryWrapper })

  await screen.findByText('Октябрь')
  expect(screen.queryByText(/без курса/)).not.toBeInTheDocument()
})

it('shows an empty state for categories', async () => {
  mockApi({ categories: [] })
  render(<Dashboard />, { wrapper: QueryWrapper })

  expect(await screen.findByText('Трат за этот период нет')).toBeInTheDocument()
})

it('shows an error in the failed block only', async () => {
  mockApi({ summaryStatus: 500 })
  render(<Dashboard />, { wrapper: QueryWrapper })

  expect(await screen.findByText('Не удалось загрузить суммы')).toBeInTheDocument()
  // Other blocks still work.
  expect(await screen.findByText('Woolworths')).toBeInTheDocument()
  expect(within(screen.getByRole('alert')).getByText('Не удалось загрузить суммы')).toBeInTheDocument()
})

it('shows a red chip per bank with a failed import', async () => {
  mockApi({
    failedImports: [
      { source: 'CommBank', uploaded_at: '2026-10-24T01:00:00Z' },
      { source: 'BCC', uploaded_at: '2026-10-23T01:00:00Z' },
    ],
  })
  render(<Dashboard />, { wrapper: QueryWrapper })

  expect(await screen.findByText('CommBank: ошибка выписки')).toBeInTheDocument()
  expect(screen.getByText('BCC: ошибка выписки')).toBeInTheDocument()
})

it('shows a chip for stuck imports', async () => {
  mockApi({ stuckPending: 2 })
  render(<Dashboard />, { wrapper: QueryWrapper })

  expect(await screen.findByText('Зависшие выписки · 2')).toBeInTheDocument()
})

it('renders accounts with the same name without key warnings', async () => {
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  mockApi({
    accounts: [
      { name: 'Savings', last_date: '2026-10-22', days: 2, level: 'ok' },
      { name: 'Savings', last_date: '2026-10-10', days: 14, level: 'bad' },
    ],
  })
  render(<Dashboard />, { wrapper: QueryWrapper })

  expect(await screen.findAllByText(/Savings/)).toHaveLength(2)
  expect(consoleError).not.toHaveBeenCalled()
  consoleError.mockRestore()
})
