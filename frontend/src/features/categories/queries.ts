import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import { queryClient } from '@/app/query'

export const categoriesKey = ['categories'] as const

export async function collectCategoryPages<T>(loadPage: (page: number) => Promise<T[]>) {
  const result: T[] = []
  for (let page = 1; ; page++) {
    const items = await loadPage(page)
    result.push(...items)
    if (items.length < 100) return result
  }
}

export function useCategories() {
  return useQuery({
    queryKey: categoriesKey,
    queryFn: ({ signal }) => collectCategoryPages(async page => unwrap(await api.GET('/api/v1/categories/', {
      params: { query: { page, per_page: 100 } },
      signal,
    }))),
  })
}

export async function invalidateFinance(includeCategories = false) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['transactions'] }),
    queryClient.invalidateQueries({ queryKey: ['reports'] }),
    ...(includeCategories ? [queryClient.invalidateQueries({ queryKey: categoriesKey })] : []),
  ])
}
