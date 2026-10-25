import createClient from 'openapi-fetch'
import type { paths } from './schema'
import { redirectToLogin } from './redirect'

// Same-origin requests. An absolute base URL (instead of '') is needed because
// the Request constructor in Node/jsdom rejects relative URLs, so tests would fail.
//
// openapi-fetch grabs globalThis.fetch once, when the client is created. The
// wrapper looks fetch up on every call instead, so tests can stub it later.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => fetch(request),
})

// The session expired (or the user never logged in): go to the Django login page.
api.use({
  onResponse({ response }) {
    if (response.status === 401) {
      redirectToLogin()
    }
  },
})
