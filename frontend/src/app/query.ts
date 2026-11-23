import { QueryClient } from '@tanstack/react-query'

export const sessionKey = ['session'] as const
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: 15_000 },
    mutations: { retry: false },
  },
})

export function clearAccount() {
  queryClient.setQueryData(sessionKey, null)
  queryClient.removeQueries({ predicate: query => query.queryKey[0] !== sessionKey[0] })
}
