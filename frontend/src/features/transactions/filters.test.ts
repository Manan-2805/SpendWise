import { describe, expect, it } from 'vitest'
import { readFilters, rangeError } from './filters'

describe('transaction URL filters', () => {
  it('preserves server search, sort, exact bounds and page', () => {
    const query = new URLSearchParams('search=Coffee+%26+tea&sort_by=amount&sort_order=asc&page=2&min_amount=2.45')
    expect(readFilters(query)).toMatchObject({ search: 'Coffee & tea', sort_by: 'amount', sort_order: 'asc', page: 2, min_amount: '2.45' })
  })
  it('reports invalid ranges without sending invalid parameters', () => {
    const query = new URLSearchParams('date_from=2026-11-29&date_to=2026-11-01&min_amount=9.95&max_amount=9.94&page=-2')
    expect(rangeError(query)).toMatch(/date/i)
    expect(readFilters(query)).not.toHaveProperty('date_from')
    expect(readFilters(query)).not.toHaveProperty('min_amount')
    expect(readFilters(query).page).toBe(1)
  })
})
