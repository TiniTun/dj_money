import { afterEach, expect, it, vi } from 'vitest'
import { api } from './client'
import { redirectToLogin } from './redirect'

vi.mock('./redirect', () => ({ redirectToLogin: vi.fn() }))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it('redirects to Django login on 401', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))
  await api.GET('/api/me')
  expect(redirectToLogin).toHaveBeenCalled()
})

it('does not redirect on a successful response', async () => {
  const body = { username: 'u', default_currency: 'AUD', currencies: ['AUD'] }
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  const { data } = await api.GET('/api/me')
  expect(data).toEqual(body)
  expect(redirectToLogin).not.toHaveBeenCalled()
})
