import { describe, expect, it } from 'vitest'
import { changePercent, formatMoney, levelClass, monthDative, monthName } from './format'

describe('format', () => {
  it('formats cards without and lists with cents', () => {
    expect(formatMoney(2480.4, 'AUD', 0)).toMatch(/2\s?480/)
    expect(formatMoney(31.5, 'AUD', 2)).toMatch(/31,50/)
  })

  it('changePercent returns null when previous is zero', () => {
    expect(changePercent(100, 0)).toBeNull()
    expect(changePercent(108, 100)).toBe(8)
  })

  it('changePercent is negative when spending went down', () => {
    expect(changePercent(90, 100)).toBe(-10)
  })

  it('monthDative', () => {
    expect(monthDative(0)).toBe('январю')
    expect(monthDative(8)).toBe('сентябрю')
    expect(monthDative(11)).toBe('декабрю')
  })

  it('monthName is a capitalized nominative', () => {
    expect(monthName(9)).toBe('Октябрь')
  })

  it('levelClass gives a distinct color per level', () => {
    const classes = (['ok', 'warn', 'bad'] as const).map(levelClass)
    expect(new Set(classes).size).toBe(3)
  })
})
