import { useState } from 'react'
import type { components } from '@/api/schema'

type MeOut = components['schemas']['MeOut']

const STORAGE_KEY = 'dj_money.currency'

// localStorage can throw (private mode, blocked site data), so every access is wrapped.
function readStoredCurrency(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStoredCurrency(code: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, code)
  } catch {
    // The choice just won't be remembered.
  }
}

// Returns the selected currency and a setter. Until `me` is loaded the
// currency is an empty string. The API guarantees that `default_currency`
// is one of `currencies`.
export function useCurrency(me: MeOut | undefined): [string, (code: string) => void] {
  const [stored, setStored] = useState(readStoredCurrency)

  const currency = me && stored && me.currencies.includes(stored) ? stored : (me?.default_currency ?? '')

  function setCurrency(code: string) {
    setStored(code)
    writeStoredCurrency(code)
  }

  return [currency, setCurrency]
}
