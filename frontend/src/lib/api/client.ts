import createClient from 'openapi-fetch'
import { toast } from 'sonner'
import { clearAccount } from '@/app/query'
import type { paths, components } from './generated'
import { browserRefreshLock, createApiTransport, parseApiError } from './transport'

const origin = location.origin

export const api = createClient<paths>({
  baseUrl: origin,
  credentials: 'include',
  fetch: createApiTransport({
    origin,
    expire: clearAccount,
    lock: browserRefreshLock(),
    waiting: () => {
      const id = toast.loading('SpendWise is busy. Retrying shortly…')
      return () => { toast.dismiss(id) }
    },
  }),
})

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (!result.response.ok) throw parseApiError(result.response, result.error)
  return result.data as T
}

export async function discardSessionBody(result: {
  data?: ReadableStream | null
  error?: unknown
  response: Response
}) {
  if (!result.response.ok) throw parseApiError(result.response, result.error)
  await result.data?.cancel()
}

export type User = components['schemas']['UserResponse']
export type Transaction = components['schemas']['TransactionResponse']
export type Category = components['schemas']['CategoryResponse']
