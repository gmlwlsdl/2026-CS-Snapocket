/** GET /search → data.items[] */
export interface SearchItem {
  id: string
  title: string
  category: string
  summary: string
  tags: string[]
  highlight: string
  score?: number | null
}

/** GET /search query params */
export interface SearchParams {
  keyword: string
  category?: string
  page?: number
  size?: number
}

export interface SearchStatus {
  aiAvailable: boolean
  aiLive: boolean
  reason: string
}

export interface SearchQueryResponse {
  modeUsed: 'text' | 'semantic'
  aiAvailable: boolean
  items: SearchItem[]
}
