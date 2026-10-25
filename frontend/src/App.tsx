import { useMe } from '@/api/queries'
import { CurrencySwitcher } from '@/components/CurrencySwitcher'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { useCurrency } from '@/hooks/useCurrency'

function App() {
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
      {isError && (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>Не удалось загрузить данные. Попробуйте обновить страницу.</AlertDescription>
        </Alert>
      )}
    </div>
  )
}

export default App
