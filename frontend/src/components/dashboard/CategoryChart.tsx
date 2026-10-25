import { useState } from 'react'
import { Bar, BarChart, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { useCategories } from '@/api/queries'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { formatMoney } from '@/lib/format'

type CategoryChartProps = {
  currency: string
}

type Period = 'week' | 'month'

const BAR_COLOR = '#2563eb'
const UNCATEGORIZED_COLOR = '#9ca3af'
const ROW_HEIGHT = 32

export function CategoryChart({ currency }: CategoryChartProps) {
  const [period, setPeriod] = useState<Period>('month')
  const { data, isPending, isError } = useCategories(currency, period)

  // The API sends "Без категории" (id = null) last; it is painted gray.
  const rows = data?.items.map((item) => ({
    name: item.name,
    amount: item.amount,
    fill: item.id === null ? UNCATEGORIZED_COLOR : BAR_COLOR,
  }))

  return (
    <Card size="sm">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>По категориям</CardTitle>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={period}
          // Clicking the selected item gives an empty value: ignore it, one period is always chosen.
          onValueChange={(value) => {
            if (value === 'week' || value === 'month') setPeriod(value)
          }}
        >
          <ToggleGroupItem value="week">Неделя</ToggleGroupItem>
          <ToggleGroupItem value="month">Месяц</ToggleGroupItem>
        </ToggleGroup>
      </CardHeader>
      <CardContent>
        {isError ? (
          <Alert variant="destructive">
            <AlertDescription>Не удалось загрузить категории</AlertDescription>
          </Alert>
        ) : isPending || !rows ? (
          <Skeleton className="h-48" />
        ) : rows.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Трат за этот период нет</p>
        ) : (
          <ResponsiveContainer width="100%" height={rows.length * ROW_HEIGHT + 8}>
            <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 0 }}>
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tickLine={false}
                axisLine={false}
                interval={0}
                tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
              />
              <Bar dataKey="amount" barSize={10} radius={4} isAnimationActive={false}>
                <LabelList
                  dataKey="amount"
                  position="right"
                  fill="var(--foreground)"
                  fontSize={12}
                  formatter={(value) => formatMoney(Number(value), currency, 0)}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
