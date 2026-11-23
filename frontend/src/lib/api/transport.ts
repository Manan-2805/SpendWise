export interface FieldIssue {
  field: string
  message: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly requestId?: string
  readonly retryAfter?: number
  readonly fields: FieldIssue[]

  constructor(message: string, options: {
    status: number
    code?: string
    requestId?: string
    retryAfter?: number
    fields?: FieldIssue[]
  }) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code
    this.requestId = options.requestId
    this.retryAfter = options.retryAfter
    this.fields = options.fields ?? []
  }
}

function object(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}

function string(value: unknown) {
  return typeof value === 'string' && value ? value : undefined
}

function retryDelay(value: unknown) {
  if (typeof value !== 'string' && typeof value !== 'number') return undefined
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined
}

export function parseApiError(response?: Response, body?: unknown) {
  if (!response) return new ApiError('Check your connection and try again.', { status: 0, code: 'NETWORK_ERROR' })
  const error = object(body)
  const fields = Array.isArray(error.errors) ? error.errors.flatMap((issue: unknown) => {
    const { field, message } = object(issue)
    return typeof field === 'string' && typeof message === 'string' ? [{ field, message }] : []
  }) : []
  const delay = retryDelay(response.headers.get('Retry-After')) ?? retryDelay(error.retry_after)
  const detail = string(error.detail)
  const message = response.status === 429
    ? delay ? `Too many requests. Try again in ${Math.ceil(delay)} seconds.` : 'Too many requests. Wait a moment and try again.'
    : response.status === 503
      ? 'SpendWise is busy. Try again shortly.'
      : detail ?? 'The request could not be completed. Try again.'
  return new ApiError(message, {
    status: response.status,
    code: string(error.code),
    requestId: string(error.request_id) ?? response.headers.get('X-Correlation-ID') ?? undefined,
    retryAfter: delay,
    fields,
  })
}

const prefix = '/api/v1'
const publicPaths = new Set(['login', 'register', 'forgot-password', 'reset-password', 'verify-email', 'refresh']
  .map(path => `${prefix}/auth/${path}`))

type RefreshLock = (work: () => Promise<boolean>) => Promise<boolean>

export function browserRefreshLock(): RefreshLock | undefined {
  return typeof navigator !== 'undefined' && navigator.locks
    ? async work => await navigator.locks.request('spendwise-session-refresh', work)
    : undefined
}

function wait(delay: number, signal: AbortSignal) {
  signal.throwIfAborted()
  return new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer)
      reject(signal.reason)
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, delay)
    signal.addEventListener('abort', abort, { once: true })
  })
}

interface TransportOptions {
  origin: string
  expire: () => void
  lock?: RefreshLock
  waiting?: () => (() => void) | void
  pause?: (delay: number, signal: AbortSignal) => Promise<void>
}

export function createApiTransport({ origin, expire, lock, waiting, pause = wait }: TransportOptions) {
  let flight: Promise<boolean> | undefined
  let generation = 0
  let recovered = true

  async function rotate() {
    const refresh = async () => {
      const response = await fetch(origin + prefix + '/auth/refresh', { method: 'POST', credentials: 'include' })
      await response.body?.cancel()
      return response.ok
    }
    if (!lock) return refresh()
    return lock(async () => {
      const check = await fetch(origin + prefix + '/auth/me', { credentials: 'include', cache: 'no-store' })
      await check.body?.cancel()
      if (check.ok) return true
      return check.status === 401 && refresh()
    })
  }

  function recover(start: number) {
    if (start !== generation) return Promise.resolve(recovered)
    if (!flight) {
      flight = rotate().catch(() => false).then(success => {
        generation++
        recovered = success
        if (!success) expire()
        return success
      }).finally(() => { flight = undefined })
    }
    return flight
  }

  return async (input: Request) => {
    const request = new Request(input, { credentials: 'include' })
    const path = new URL(request.url).pathname
    const protectedEndpoint = !publicPaths.has(path) && !path.startsWith(prefix + '/health')
    const safeRead = request.method === 'GET' && path !== prefix + '/auth/verify-email'
    const start = generation
    try {
      // A GET can be cloned for bounded retries without consuming a mutation body.
      const send = () => fetch(safeRead ? request.clone() : request)
      let response = await send()
      let retriedAuth = false
      let retriedOverload = false

      while (true) {
        if (response.status === 401 && protectedEndpoint && !retriedAuth) {
          const success = await recover(start)
          if (!success) return response
          await response.body?.cancel()
          if (!safeRead) throw new ApiError('Your session was renewed. Submit this change again.', { status: 401, code: 'RETRY_WRITE' })
          retriedAuth = true
          response = await send()
          if (response.status === 401) {
            expire()
            return response
          }
        }
        const delay = retryDelay(response.headers.get('Retry-After'))
        if (response.status !== 503 || !safeRead || retriedOverload || delay === undefined || delay > 60) return response
        retriedOverload = true
        const dismiss = waiting?.()
        try {
          await response.body?.cancel()
          await pause(delay * 1000, request.signal)
        } finally {
          dismiss?.()
        }
        response = await send()
      }
    } catch (error) {
      if (request.signal.aborted || error instanceof ApiError) throw error
      throw parseApiError()
    }
  }
}
