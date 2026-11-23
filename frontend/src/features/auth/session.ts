import { useQuery } from '@tanstack/react-query'
import { clearAccount, queryClient, sessionKey } from '@/app/query'
import { api, unwrap } from '@/lib/api/client'
import { ApiError } from '@/lib/api/transport'

async function readSession({ signal }: { signal?: AbortSignal } = {}) {
  try {
    return unwrap(await api.GET('/api/v1/auth/me', { signal }))
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function useSession() {
  return useQuery({ queryKey: sessionKey, queryFn: readSession, staleTime: 60_000 })
}

export async function loadSignedInUser() {
  const user = await readSession()
  clearAccount()
  queryClient.setQueryData(sessionKey, user)
  if (!user) throw new Error('The browser could not establish a session. Try signing in again.')
  return user
}
