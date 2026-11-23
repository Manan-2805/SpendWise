import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { createApiTransport, parseApiError } from './transport'

const origin = 'http://localhost:3000'
const profile = origin + '/api/v1/users/me'
const refresh = origin + '/api/v1/auth/refresh'
const session = origin + '/api/v1/auth/me'
const server = setupServer()
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterAll(() => server.close())
afterEach(() => { server.resetHandlers(); vi.restoreAllMocks() })
let expire: ReturnType<typeof vi.fn<() => void>>
beforeEach(() => { expire = vi.fn<() => void>() })

describe('API transport', () => {
  it('shares concurrent refresh, replays reads once and sends only cookies', async () => {
    const dispatched = vi.spyOn(globalThis, 'fetch')
    let signedIn = false
    let rotations = 0
    server.use(
      http.get(profile, ({ request }) => {
        expect(request.headers.has('Authorization')).toBe(false)
        return new HttpResponse(null, { status: signedIn ? 200 : 401 })
      }),
      http.post(refresh, async () => {
        rotations++
        await new Promise(resolve => setTimeout(resolve, 10))
        signedIn = true
        return HttpResponse.json({ access_token: 'test-placeholder' })
      }),
    )
    const transport = createApiTransport({ origin, expire })
    const results = await Promise.all([transport(new Request(profile)), transport(new Request(profile))])
    expect(results.map(result => result.status)).toEqual([200, 200])
    expect(rotations).toBe(1)
    expect(dispatched.mock.calls.some(([request]) => request instanceof Request && request.url === profile && request.credentials === 'include')).toBe(true)
  })

  it('uses the completed recovery for a staggered 401', async () => {
    let releaseSlow = () => {}
    const slow = new Promise<void>(resolve => { releaseSlow = resolve })
    let signedIn = false
    let rotations = 0
    server.use(
      http.get(profile, async ({ request }) => {
        const status = signedIn ? 200 : 401
        if (status === 401 && new URL(request.url).searchParams.has('slow')) await slow
        return new HttpResponse(null, { status })
      }),
      http.post(refresh, () => {
        rotations++
        signedIn = true
        return new HttpResponse(null, { status: 200 })
      }),
    )
    const transport = createApiTransport({ origin, expire })
    const later = transport(new Request(profile + '?slow'))
    try {
      expect((await transport(new Request(profile))).status).toBe(200)
    } finally {
      releaseSlow()
    }
    expect((await later).status).toBe(200)
    expect(rotations).toBe(1)
  })

  it('checks the session inside the Web Lock and skips rotation when already valid', async () => {
    let locked = false
    let reads = 0
    const lock = vi.fn(async (work: () => Promise<boolean>) => {
      locked = true
      return work()
    })
    server.use(
      http.get(profile, () => new HttpResponse(null, { status: ++reads === 1 ? 401 : 200 })),
      http.get(session, () => {
        expect(locked).toBe(true)
        return new HttpResponse(null, { status: 200 })
      }),
    )
    const transport = createApiTransport({ origin, expire, lock })
    expect((await transport(new Request(profile))).status).toBe(200)
    expect(lock).toHaveBeenCalledTimes(1)
  })

  it('never replays writes and clears account state when refresh fails', async () => {
    let writes = 0
    server.use(
      http.patch(profile, () => { writes++; return new HttpResponse(null, { status: 401 }) }),
      http.post(refresh, () => new HttpResponse(null, { status: 401 })),
    )
    const transport = createApiTransport({ origin, expire })
    expect((await transport(new Request(profile, { method: 'PATCH' }))).status).toBe(401)
    expect(writes).toBe(1)
    expect(expire).toHaveBeenCalledTimes(1)
  })

  it('waits and retries a safe overload once, leaving verification and writes manual', async () => {
    let reads = 0
    const verify = origin + '/api/v1/auth/verify-email'
    const overload = () => HttpResponse.json({ code: 'OVERLOADED' }, { status: 503, headers: { 'Retry-After': '1' } })
    server.use(
      http.get(profile, () => ++reads === 1 ? overload() : new HttpResponse(null, { status: 200 })),
      http.get(verify, overload),
      http.patch(profile, overload),
    )
    const waiting = vi.fn()
    const pause = vi.fn(async () => {})
    const transport = createApiTransport({ origin, expire, waiting, pause })
    expect((await transport(new Request(profile))).status).toBe(200)
    expect((await transport(new Request(verify))).status).toBe(503)
    expect((await transport(new Request(profile, { method: 'PATCH' }))).status).toBe(503)
    expect(pause).toHaveBeenCalledExactlyOnceWith(1000, expect.anything())
    expect(waiting).toHaveBeenCalledTimes(1)
  })

  it('normalizes field, request ID, quota, network and non-JSON errors', () => {
    expect(parseApiError(new Response(null, { status: 422, headers: { 'X-Correlation-ID': 'id' } }), {
      detail: 'Request validation failed',
      code: 'VALIDATION_ERROR',
      errors: [{ field: 'amount', message: 'Required', type: 'missing' }],
    })).toMatchObject({ status: 422, requestId: 'id', fields: [{ field: 'amount', message: 'Required' }] })
    expect(parseApiError(new Response(null, { status: 429 }), { retry_after: 5 }))
      .toMatchObject({ status: 429, retryAfter: 5 })
    expect(parseApiError(new Response(null, { status: 503 }), '<html>')).toMatchObject({ status: 503 })
    expect(parseApiError()).toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
  })
})
