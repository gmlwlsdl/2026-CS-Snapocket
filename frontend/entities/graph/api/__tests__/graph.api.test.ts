// FIRST:
//   Fast        — MSW 인메모리 처리, 실제 IO 없음
//   Independent — beforeEach에서 토큰 설정, afterEach에서 자동 초기화
//   Repeatable  — 결정적 MSW 응답
//   Self-Val.   — variables 전달·GraphQL 에러(200 + errors)·HTTP 에러 모두 expect()로 검증
//   Timely      — graph.api.ts 에러 처리 로직 확인 후 작성

import { describe, it, expect, beforeEach } from 'vitest'
import { server } from '../../../../__mocks__/server'
import { http, HttpResponse } from 'msw'
import { getNodes, getGraph, searchNodes, getGraphSummary } from '../graph.api'
import { ApiError } from '@/shared/api'

const TOKEN = 'graph-test-token'

beforeEach(() => {
  localStorage.setItem('access_token', TOKEN)
})

// ─── getNodes ─────────────────────────────────────────────────────────────────

describe('getNodes', () => {
  it('GraphQL POST를 보내고 nodes 배열을 반환한다', async () => {
    const nodes = await getNodes()
    expect(Array.isArray(nodes)).toBe(true)
    expect(nodes[0]).toMatchObject({ id: 'n1', title: '노드1' })
  })

  it('category를 전달하면 variables에 포함시킨다', async () => {
    let capturedVariables: Record<string, unknown> = {}
    server.use(
      http.post('http://localhost/api/graphql', async ({ request }) => {
        const body = await request.json() as { query: string; variables: Record<string, unknown> }
        capturedVariables = body.variables ?? {}
        return HttpResponse.json({
          data: { nodes: [] },
        })
      }),
    )

    await getNodes('lecture')

    expect(capturedVariables.category).toBe('lecture')
  })

  it('category 없이 호출하면 variables가 빈 객체다', async () => {
    let capturedVariables: Record<string, unknown> = { marker: true }
    server.use(
      http.post('http://localhost/api/graphql', async ({ request }) => {
        const body = await request.json() as { query: string; variables: Record<string, unknown> }
        capturedVariables = body.variables ?? {}
        return HttpResponse.json({ data: { nodes: [] } })
      }),
    )

    await getNodes()

    expect(capturedVariables).toEqual({})
  })

  it('Authorization 헤더를 포함해 요청한다', async () => {
    let capturedAuth = ''
    server.use(
      http.post('http://localhost/api/graphql', ({ request }) => {
        capturedAuth = request.headers.get('Authorization') ?? ''
        return HttpResponse.json({ data: { nodes: [] } })
      }),
    )

    await getNodes()

    expect(capturedAuth).toBe(`Bearer ${TOKEN}`)
  })

  it('토큰 없을 때는 Authorization 헤더를 보내지 않는다', async () => {
    localStorage.clear()
    let capturedAuth: string | null = 'sentinel'
    server.use(
      http.post('http://localhost/api/graphql', ({ request }) => {
        capturedAuth = request.headers.get('Authorization')
        return HttpResponse.json({ data: { nodes: [] } })
      }),
    )

    await getNodes()

    expect(capturedAuth).toBeNull()
  })
})

// ─── getGraph ─────────────────────────────────────────────────────────────────

describe('getGraph', () => {
  it('nodes와 edges를 함께 반환한다', async () => {
    const graph = await getGraph()
    expect(Array.isArray(graph.nodes)).toBe(true)
    expect(Array.isArray(graph.edges)).toBe(true)
  })
})

// ─── searchNodes ─────────────────────────────────────────────────────────────

describe('searchNodes', () => {
  it('검색어를 variables.q로 전달하고 결과를 반환한다', async () => {
    const results = await searchNodes('AI')
    expect(results.length).toBeGreaterThan(0)
    expect(results[0].title).toContain('AI')
  })

  it('빈 검색어면 빈 배열을 반환한다', async () => {
    const results = await searchNodes('')
    expect(results).toEqual([])
  })
})

// ─── getGraphSummary ──────────────────────────────────────────────────────────

describe('getGraphSummary', () => {
  it('REST /graph/summary를 호출하고 필드를 반환한다', async () => {
    const summary = await getGraphSummary()
    expect(summary.node_count).toBe(5)
    expect(summary.document_count).toBe(3)
    expect(summary.tag_count).toBe(8)
    expect(summary.edge_count).toBe(4)
  })
})

// ─── GraphQL 에러 처리 ────────────────────────────────────────────────────────

describe('GraphQL 에러 처리', () => {
  it('HTTP 200이지만 errors 필드가 있으면 ApiError(200)을 throw한다', async () => {
    server.use(
      http.post('http://localhost/api/graphql', () =>
        HttpResponse.json({
          data: null,
          errors: [{ message: '권한 없음', extensions: { code: 'FORBIDDEN' } }],
        }),
      ),
    )

    await expect(getNodes()).rejects.toBeInstanceOf(ApiError)
    await expect(getNodes()).rejects.toMatchObject({ status: 200, message: '권한 없음' })
  })

  it('HTTP 4xx 응답이면 ApiError(status)를 throw한다', async () => {
    server.use(
      http.post('http://localhost/api/graphql', () =>
        HttpResponse.json(
          { data: null, errors: [{ message: 'Bad Request' }] },
          { status: 400 },
        ),
      ),
    )

    await expect(getNodes()).rejects.toBeInstanceOf(ApiError)
    await expect(getNodes()).rejects.toMatchObject({ status: 400 })
  })
})
