// FIRST:
//   Fast        — MSW가 네트워크를 인메모리에서 처리, 실제 IO 없음
//   Independent — beforeEach에서 토큰 설정, afterEach에서 MSW·localStorage 자동 초기화
//   Repeatable  — 결정적 MSW 응답
//   Self-Val.   — URL 파라미터·응답 변환·camelCase 변환 모두 expect()로 검증
//   Timely      — search.api.ts 시그니처 및 응답 변환 로직 확인 후 작성

import { describe, it, expect, beforeEach } from 'vitest'
import { server } from '../../../../__mocks__/server'
import { http, HttpResponse } from 'msw'
import { searchDocuments, getSearchStatus, queryDocuments } from '../search.api'
import { ApiError } from '@/shared/api'

const TOKEN = 'search-test-token'

beforeEach(() => {
  localStorage.setItem('access_token', TOKEN)
})

// ─── searchDocuments ──────────────────────────────────────────────────────────

describe('searchDocuments', () => {
  it('keyword를 URL 파라미터로 직렬화해 items를 반환한다', async () => {
    const items = await searchDocuments({ keyword: '강의' })
    expect(items.length).toBeGreaterThan(0)
    expect(items[0].title).toContain('강의')
  })

  it('keyword, category, page, size를 모두 URL에 직렬화한다', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost/api/search', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({
          success: true, message: 'OK',
          data: { items: [] },
        })
      }),
    )

    await searchDocuments({ keyword: 'test', category: 'lecture', page: 2, size: 5 })

    expect(capturedUrl).toContain('keyword=test')
    expect(capturedUrl).toContain('category=lecture')
    expect(capturedUrl).toContain('page=2')
    expect(capturedUrl).toContain('size=5')
  })

  it('category 미입력 시 URL에 category 파라미터를 포함하지 않는다', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost/api/search', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ success: true, message: 'OK', data: { items: [] } })
      }),
    )

    await searchDocuments({ keyword: 'hi' })

    expect(capturedUrl).not.toContain('category')
  })

  it('401 응답이면 ApiError를 throw한다', async () => {
    server.use(
      http.get('http://localhost/api/search', () =>
        HttpResponse.json({ success: false, message: 'Unauthorized', data: null }, { status: 401 }),
      ),
    )

    await expect(searchDocuments({ keyword: 'x' })).rejects.toBeInstanceOf(ApiError)
  })
})

// ─── getSearchStatus ──────────────────────────────────────────────────────────

describe('getSearchStatus', () => {
  it('snake_case 응답을 camelCase로 변환해 반환한다', async () => {
    const status = await getSearchStatus()

    expect(status.aiAvailable).toBe(true)
    expect(status.aiLive).toBe(true)
    expect(status.reason).toBe('model ready')
  })

  it('ai_available=false인 응답도 올바르게 변환한다', async () => {
    server.use(
      http.get('http://localhost/api/search/status', () =>
        HttpResponse.json({
          success: true, message: 'OK',
          data: { ai_available: false, ai_live: false, reason: 'not ready' },
        }),
      ),
    )

    const status = await getSearchStatus()

    expect(status.aiAvailable).toBe(false)
    expect(status.aiLive).toBe(false)
    expect(status.reason).toBe('not ready')
  })
})

// ─── queryDocuments ───────────────────────────────────────────────────────────

describe('queryDocuments', () => {
  it('mode를 생략하면 URL에 mode=auto가 포함된다', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost/api/search/query', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({
          success: true, message: 'OK',
          data: { mode_requested: 'auto', mode_used: 'text', ai_available: false, items: [] },
        })
      }),
    )

    await queryDocuments({ keyword: 'hello' })

    expect(capturedUrl).toContain('mode=auto')
  })

  it('mode를 명시하면 URL에 그 값이 포함된다', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost/api/search/query', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({
          success: true, message: 'OK',
          data: { mode_requested: 'semantic', mode_used: 'semantic', ai_available: true, items: [] },
        })
      }),
    )

    await queryDocuments({ keyword: 'AI', mode: 'semantic' })

    expect(capturedUrl).toContain('mode=semantic')
  })

  it('응답의 mode_used와 ai_available을 camelCase로 변환해 반환한다', async () => {
    server.use(
      http.get('http://localhost/api/search/query', () =>
        HttpResponse.json({
          success: true, message: 'OK',
          data: { mode_requested: 'auto', mode_used: 'semantic', ai_available: true, items: [] },
        }),
      ),
    )

    const result = await queryDocuments({ keyword: 'graph' })

    expect(result.modeUsed).toBe('semantic')
    expect(result.aiAvailable).toBe(true)
    expect(Array.isArray(result.items)).toBe(true)
  })
})
