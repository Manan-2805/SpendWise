import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import { monthBounds } from '@/lib/dates'
import type { components } from '@/lib/api/generated'

export type CategoryShare = components['schemas']['CategoryBreakdownResponse']

export function useMonthlySummary(month: string) {
  const { year, month: number } = monthBounds(month)
  return useQuery({
    queryKey: ['reports', 'summary', month],
    queryFn: async ({ signal }) => unwrap(await api.GET('/api/v1/reports/monthly-summary', { signal, params: { query: { year, month: number } } })),
  })
}

export function useCategoryBreakdown(month: string, type: 'income' | 'expense') {
  const { date_from, date_to } = monthBounds(month)
  return useQuery({
    queryKey: ['reports', 'categories', month, type],
    queryFn: async ({ signal }) => unwrap(await api.GET('/api/v1/reports/category-breakdown', {
      signal, params: { query: { date_from, date_to, type } },
    })),
  })
}
