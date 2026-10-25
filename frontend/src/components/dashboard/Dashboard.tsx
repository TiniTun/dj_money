import { useMe } from '@/api/queries'
import { CurrencySwitcher } from '@/components/CurrencySwitcher'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { useCurrency } from '@/hooks/useCurrency'
import { CategoryChart } from './CategoryChart'
import { RecentTransactions } from './RecentTransactions'
import { StatusChips } from './StatusChips'
import { SummaryCards, UnconvertedWarning } from './SummaryCards'

// The home screen. The selected currency lives here: it is needed by the
// switcher in the header and by every block below it.
export function Dashboard() {
  const { data: me, isError } = useMe()
  const [currency, setCurrency] = useCurrency(me)

  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">DJ Money</h1>
        {me ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">{me.username}</span>
            <CurrencySwitcher value={currency} options={me.currencies} onChange={setCurrency} />
          </div>
        ) : isError ? null : (
          <Skeleton className="h-8 w-40" />
        )}
      </header>

      {isError ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>Не удалось загрузить данные. Попробуйте обновить страницу.</AlertDescription>
        </Alert>
      ) : (
        <main className="mt-4 flex flex-col gap-4">
          <SummaryCards currency={currency} />
          <StatusChips />
          <UnconvertedWarning currency={currency} />
          <div className="grid gap-4 md:grid-cols-2">
            <CategoryChart currency={currency} />
            <RecentTransactions currency={currency} />
          </div>
        </main>
      )}
    </div>
  )
}
