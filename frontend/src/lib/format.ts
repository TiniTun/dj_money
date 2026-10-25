// Amount in the given currency, e.g. "2 480 A$". Cards use 0 fraction digits,
// transaction lists use 2.
export function formatMoney(amount: number, currency: string, fractionDigits: 0 | 2): string {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(amount)
}

// How much `current` differs from `previous`, in whole percent.
// null when there is nothing to compare with.
export function changePercent(current: number, previous: number): number | null {
  if (previous === 0) return null
  return Math.round(((current - previous) / previous) * 100)
}

const MONTHS_DATIVE = [
  'январю',
  'февралю',
  'марту',
  'апрелю',
  'маю',
  'июню',
  'июлю',
  'августу',
  'сентябрю',
  'октябрю',
  'ноябрю',
  'декабрю',
]

// "к сентябрю": monthIndex is 0 for January ... 11 for December.
export function monthDative(monthIndex: number): string {
  return MONTHS_DATIVE[monthIndex]
}

// "Октябрь": the month name in the nominative case, capitalized.
export function monthName(monthIndex: number): string {
  const name = new Intl.DateTimeFormat('ru-RU', { month: 'long' }).format(new Date(2000, monthIndex, 1))
  return name.charAt(0).toUpperCase() + name.slice(1)
}

// Text color of the status dot: green, amber or red.
export function levelClass(level: 'ok' | 'warn' | 'bad'): string {
  switch (level) {
    case 'ok':
      return 'text-green-600'
    case 'warn':
      return 'text-amber-500'
    case 'bad':
      return 'text-red-600'
  }
}
