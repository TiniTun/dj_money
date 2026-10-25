import { useStatus } from '@/api/queries'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { levelClass } from '@/lib/format'

type Level = 'ok' | 'warn' | 'bad'

type ChipProps = {
  level: Level
  children: string
}

function Chip({ level, children }: ChipProps) {
  return (
    <Badge variant="outline" className="h-6 gap-1.5 px-2.5 text-xs font-normal">
      <span aria-hidden="true" className={levelClass(level)}>
        ●
      </span>
      {children}
    </Badge>
  )
}

// "2026-10-24" -> "24.10"
function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split('-')
  return `${day}.${month}`
}

export function StatusChips() {
  const { data: status, isPending, isError } = useStatus()

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Не удалось загрузить статусы данных</AlertDescription>
      </Alert>
    )
  }

  if (isPending) {
    return <Skeleton className="h-6 w-full max-w-md" />
  }

  return (
    <div className="flex flex-wrap gap-2">
      {status.accounts.map((account) => (
        <Chip key={account.name} level={account.level}>
          {`${account.name} · ${account.days} дн.`}
        </Chip>
      ))}
      <Chip level={status.rates.level}>
        {status.rates.last_date ? `Курсы · ${shortDate(status.rates.last_date)}` : 'Курсы · нет данных'}
      </Chip>
      {status.uncategorized.count > 0 && (
        <Chip level={status.uncategorized.level}>{`Без категории · ${status.uncategorized.count}`}</Chip>
      )}
      {status.failed_imports.length > 0 && (
        <Chip level="bad">{`Ошибка выписки · ${status.failed_imports.length}`}</Chip>
      )}
      {status.stuck_pending > 0 && <Chip level="warn">{`Зависшие выписки · ${status.stuck_pending}`}</Chip>}
    </div>
  )
}
