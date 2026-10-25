import { useQuery } from '@tanstack/react-query'
import { api } from './client'

// openapi-fetch does not throw on HTTP errors: it returns `data` only for 2xx
// responses, so a missing `data` means the request failed. We throw then,
// so that TanStack Query puts the query into the error state.

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const { data, response } = await api.GET('/api/me')
      if (!data) throw new Error(`GET /api/me failed: ${response.status}`)
      return data
    },
  })
}

export function useSummary(currency: string) {
  return useQuery({
    queryKey: ['summary', currency],
    queryFn: async () => {
      const { data, response } = await api.GET('/api/dashboard/summary', {
        params: { query: { currency } },
      })
      if (!data) throw new Error(`GET /api/dashboard/summary failed: ${response.status}`)
      return data
    },
  })
}

export function useCategories(currency: string, period: 'week' | 'month') {
  return useQuery({
    queryKey: ['categories', currency, period],
    queryFn: async () => {
      const { data, response } = await api.GET('/api/dashboard/categories', {
        params: { query: { currency, period } },
      })
      if (!data) throw new Error(`GET /api/dashboard/categories failed: ${response.status}`)
      return data
    },
  })
}

export function useRecent(currency: string) {
  return useQuery({
    queryKey: ['recent', currency],
    queryFn: async () => {
      const { data, response } = await api.GET('/api/dashboard/transactions/recent', {
        params: { query: { currency } },
      })
      if (!data) throw new Error(`GET /api/dashboard/transactions/recent failed: ${response.status}`)
      return data
    },
  })
}

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: async () => {
      const { data, response } = await api.GET('/api/dashboard/status')
      if (!data) throw new Error(`GET /api/dashboard/status failed: ${response.status}`)
      return data
    },
  })
}
