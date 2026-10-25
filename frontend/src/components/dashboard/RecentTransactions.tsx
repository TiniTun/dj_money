import { useRecent, useSummary } from '@/api/queries'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatMoney } from '@/lib/format'

type RecentTransactionsProps = {
  currency: string
}

// The API returns only today's and yesterday's spending, so the groups are
// "Сегодня" and "Вчера". "Today" is the dashboard's date (as_of), which may
// differ from the browser's date because of the time zone.
function dayLabel(date: string, today: string | undefined): string {
  if (today === undefined) return date
  return date === today ? 'Сегодня' : 'Вчера'
}

export function RecentTransactions({ currency }: RecentTransactionsProps) {
  const { data, isPending, isError } = useRecent(currency)
  const today = useSummary(currency).data?.as_of

  let content
  if (isError) {
    content = (
      <Alert variant="destructive">
        <AlertDescription>Не удалось загрузить последние траты</AlertDescription>
      </Alert>
    )
  } else if (isPending) {
    content = <Skeleton className="h-48" />
  } else if (data.items.length === 0) {
    content = <p className="py-8 text-center text-sm text-muted-foreground">Трат за сегодня и вчера нет</p>
  } else {
    // Items come sorted by date (newest first), so a new group starts when the date changes.
    const dates = [...new Set(data.items.map((item) => item.date))]
    content = dates.map((date) => (
      <section key={date} className="mt-3 first:mt-0">
        <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {dayLabel(date, today)}
        </h3>
        <ul>
          {data.items
            .filter((item) => item.date === date)
            .map((item) => {
              // Without a rate there is no converted amount: show the original one as the main amount.
              const showOriginal = item.original_currency !== null && (item.amount === null || item.original_currency !== currency)
              const original =
                item.original_currency !== null ? formatMoney(item.original_amount, item.original_currency, 2) : ''
              return (
                <li key={item.id} className="flex items-start justify-between gap-3 border-b py-2 text-sm last:border-b-0">
                  <div className="min-w-0">
                    <div className="truncate">{item.title}</div>
                    <div className="text-xs text-muted-foreground">{item.category ?? '—'}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div>{item.amount !== null ? formatMoney(item.amount, currency, 2) : 'нет курса'}</div>
                    {showOriginal && <div className="text-xs text-muted-foreground">{original}</div>}
                  </div>
                </li>
              )
            })}
        </ul>
      </section>
    ))
  }

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Последние траты</CardTitle>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
