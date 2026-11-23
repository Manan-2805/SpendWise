import type { operations } from '@/lib/api/generated'
import { compareAmounts, validRangeAmount } from '@/lib/amount'
import { isDate } from '@/lib/dates'

export const filterNames = ['search', 'type', 'category_id', 'date_from', 'date_to', 'min_amount', 'max_amount', 'sort_by', 'sort_order'] as const
type Filters = NonNullable<operations['list_transactions_api_v1_transactions__get']['parameters']['query']>

function seedPositiveNumber(value: string | null) {
  if (!value || !/^\d+$/.test(value)) return undefined
  const number = Number(value)
  return Number.isSafeInteger(number) && number > 0 ? number : undefined
}

export function rangeError(params: URLSearchParams) {
  const minimum = params.get('min_amount')
  const maximum = params.get('max_amount')
  const from = params.get('date_from')
  const to = params.get('date_to')
  if ((from && !isDate(from)) || (to && !isDate(to))) return 'Enter valid dates.'
  if (from && to && from > to) return 'The start date must be on or before the end date.'
  if ((minimum && !validRangeAmount(minimum)) || (maximum && !validRangeAmount(maximum))) return 'Enter positive decimal amounts.'
  if (minimum && maximum && compareAmounts(minimum, maximum) > 0) return 'The minimum amount must be at or below the maximum.'
}

export function readFilters(params: URLSearchParams): Filters {
  const type = params.get('type')
  const sort = params.get('sort_by')
  const order = params.get('sort_order')
  const category = seedPositiveNumber(params.get('category_id'))
  const search = params.get('search')?.trim().slice(0, 100)
  const ranges = rangeError(params) ? {} : Object.fromEntries(
    ['date_from', 'date_to', 'min_amount', 'max_amount'].flatMap(key => {
      const value = params.get(key)
      return value ? [[key, value]] : []
    }),
  )
  return {
    page: seedPositiveNumber(params.get('page')) ?? 1,
    per_page: 20,
    ...(search ? { search } : {}),
    ...(category ? { category_id: category } : {}),
    ...(type === 'income' || type === 'expense' ? { type } : {}),
    sort_by: sort === 'amount' || sort === 'created_at' ? sort : 'transaction_date',
    sort_order: order === 'asc' ? 'asc' : 'desc',
    ...ranges,
  }
}
