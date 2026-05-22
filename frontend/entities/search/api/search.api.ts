import { apiClient } from '@/shared/api'
import type {
  SearchItem,
  SearchParams,
  SearchQueryResponse,
  SearchStatus,
} from '../model/types'

interface SearchStatusApiResponse {
  ai_available: boolean
  ai_live: boolean
  reason: string
}

interface SearchQueryApiResponse {
  mode_requested: 'auto' | 'text' | 'semantic'
  mode_used: 'text' | 'semantic'
  ai_available: boolean
  items: SearchItem[]
}

/** GET /search — 제목/요약/태그 통합 검색 */
export async function searchDocuments(params: SearchParams): Promise<SearchItem[]> {
  const query = new URLSearchParams({ keyword: params.keyword })
  if (params.category) query.set('category', params.category)
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.size !== undefined) query.set('size', String(params.size))
  const res = await apiClient<{ items: SearchItem[] }>(`/search?${query.toString()}`, {
    requireAuth: true,
  })
  return res.data.items
}

export async function getSearchStatus(): Promise<SearchStatus> {
  const res = await apiClient<SearchStatusApiResponse>('/search/status', {
    requireAuth: true,
  })
  return {
    aiAvailable: res.data.ai_available,
    aiLive: res.data.ai_live,
    reason: res.data.reason,
  }
}

export async function queryDocuments(
  params: SearchParams & { mode?: 'auto' | 'text' | 'semantic' },
): Promise<SearchQueryResponse> {
  const query = new URLSearchParams({ keyword: params.keyword })
  if (params.category) query.set('category', params.category)
  if (params.size !== undefined) query.set('size', String(params.size))
  query.set('mode', params.mode ?? 'auto')

  const res = await apiClient<SearchQueryApiResponse>(`/search/query?${query.toString()}`, {
    requireAuth: true,
  })
  return {
    modeUsed: res.data.mode_used,
    aiAvailable: res.data.ai_available,
    items: res.data.items,
  }
}
