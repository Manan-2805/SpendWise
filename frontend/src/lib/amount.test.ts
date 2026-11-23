import { describe, expect, it } from 'vitest'
import { compareAmounts, formatAmount, validAmount } from './amount'

describe('decimal money', () => {
  it('validates the API transaction bounds and keeps the wire amount as a string', () => {
    expect(validAmount('9999999999.99')).toBe(true)
    for (const value of ['0.00', '-1', '1e2', '1.001', '10000000000', '1,000']) {
      expect(validAmount(value)).toBe(false)
    }
  })

  it('compares decimal strings without rounding', () => {
    expect(compareAmounts('9007199254740993.01', '9007199254740993.02')).toBeLessThan(0)
    expect(compareAmounts('2.4', '2.40')).toBe(0)
  })

  it('localizes large signed balances without losing cents', () => {
    expect(formatAmount('9007199254740993.01', undefined, 'en-US')).toBe('9,007,199,254,740,993.01')
    expect(formatAmount('-0.01', 'USD', 'en-US')).toBe('-$0.01')
    expect(formatAmount('1234.50', undefined, 'de-DE')).toBe('1.234,50')
  })
})
