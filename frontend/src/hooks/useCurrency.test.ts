import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import type { components } from '@/api/schema'
import { useCurrency } from './useCurrency'

type MeOut = components['schemas']['MeOut']

const me: MeOut = {
  username: 'u',
  default_currency: 'AUD',
  currencies: ['AUD', 'KZT', 'USD'],
}

describe('useCurrency', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('uses the default currency when nothing is stored', () => {
    const { result } = renderHook(() => useCurrency(me))
    expect(result.current[0]).toBe('AUD')
  })

  it('falls back to default currency when stored one is no longer available', () => {
    localStorage.setItem('dj_money.currency', 'TRY')
    const { result } = renderHook(() => useCurrency(me))
    expect(result.current[0]).toBe('AUD')
  })

  it('remembers the chosen currency', () => {
    const { result } = renderHook(() => useCurrency(me))
    act(() => result.current[1]('KZT'))
    expect(result.current[0]).toBe('KZT')
    expect(localStorage.getItem('dj_money.currency')).toBe('KZT')
  })
})
