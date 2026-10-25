import { useSummary } from '@/api/queries'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { changePercent, formatMoney, monthDative, monthName } from '@/lib/format'

type SummaryCardsProps = {
  currency: string
}

type SummaryCardProps = {
  title: string
  value: string
  note?: string
}

function SummaryCard({ title, value, note }: SummaryCardProps) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-sm font-normal text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold">{value}</div>
        {/* Keeps the card height the same with or without a comparison line. */}
        <div className="min-h-4 text-xs text-muted-foreground">{note}</div>
      </CardContent>
    </Card>
  )
}

// "↑ 8% к сентябрю". Nothing when there is no previous month to compare with.
function monthComparison(month: number, previousMonthToDate: number, monthIndex: number): string | undefined {
  const percent = changePercent(month, previousMonthToDate)
  if (percent === null) return undefined
  const arrow = percent > 0 ? '↑' : percent < 0 ? '↓' : '→'
  const previousMonthIndex = (monthIndex + 11) % 12
  return `${arrow} ${Math.abs(percent)}% к ${monthDative(previousMonthIndex)}`
}

export function SummaryCards({ currency }: SummaryCardsProps) {
  const { data: summary, isPending, isError } = useSummary(currency)

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Не удалось загрузить суммы</AlertDescription>
      </Alert>
    )
  }

  if (isPending) {
    return (
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    )
  }

  // as_of is "YYYY-MM-DD" in the dashboard timezone: take the month from the text, not from a Date.
  const monthIndex = Number(summary.as_of.slice(5, 7)) - 1

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <SummaryCard title="Сегодня" value={formatMoney(summary.today, currency, 0)} />
      <SummaryCard title="Эта неделя" value={formatMoney(summary.week, currency, 0)} />
      <SummaryCard
        title={monthName(monthIndex)}
        value={formatMoney(summary.month, currency, 0)}
        note={monthComparison(summary.month, summary.previous_month_to_date, monthIndex)}
      />
    </div>
  )
}

const pluralRules = new Intl.PluralRules('ru-RU')

// "3 транзакции без курса не вошли в суммы". Renders nothing when everything was converted.
export function UnconvertedWarning({ currency }: SummaryCardsProps) {
  const { data: summary } = useSummary(currency)

  if (!summary || summary.unconverted === 0) return null

  const count = summary.unconverted
  const isOne = pluralRules.select(count) === 'one'
  const noun = { one: 'транзакция', few: 'транзакции', many: 'транзакций', other: 'транзакции' }[
    pluralRules.select(count)
  ]

  return (
    <Alert>
      <AlertDescription>
        {count} {noun} без курса не {isOne ? 'вошла' : 'вошли'} в суммы
      </AlertDescription>
    </Alert>
  )
}
