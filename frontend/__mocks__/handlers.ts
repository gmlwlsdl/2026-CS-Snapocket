import { http, HttpResponse } from 'msw'

// BASE_URL은 jsdom(브라우저) 환경에서 "/api"
// sharedhttp://localhost/api/client.ts: typeof window === "undefined" ? "http://localhost:8000" : "/api"

export const handlers = [
  // ─── Auth ───────────────────────────────────────────────────────────────────

  http.post('http://localhost/api/auth/login', async ({ request }) => {
    const body = await request.json() as { email: string; password: string }

    if (body.email === 'test@example.com' && body.password === 'password123') {
      return HttpResponse.json({
        success: true,
        message: 'Login successful',
        data: {
          access_token: 'mock-access-token',
          token_type: 'Bearer',
        },
      })
    }

    // 잘못된 자격증명은 400: apiClient가 401에서 redirectToLogin()을 호출하므로
    // 인증 실패(wrong password)와 미인증(no token)을 구분한다
    return HttpResponse.json(
      {
        success: false,
        message: '이메일 또는 비밀번호가 올바르지 않습니다.',
        data: null,
        error_code: 'INVALID_CREDENTIALS',
      },
      { status: 400 },
    )
  }),

  http.get('http://localhost/api/auth/me', ({ request }) => {
    const auth = request.headers.get('Authorization')
    if (!auth) {
      return HttpResponse.json(
        { success: false, message: 'Unauthorized', data: null },
        { status: 401 },
      )
    }
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: {
        id: 'user-1',
        email: 'test@example.com',
        name: '테스트 유저',
      },
    })
  }),

  http.post('http://localhost/api/auth/logout', () => {
    return HttpResponse.json({ success: true, message: 'OK', data: null })
  }),

  // ─── Documents ──────────────────────────────────────────────────────────────

  http.post('http://localhost/api/documents/upload', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: {
        document_id: 'doc-123',
        file_url: '/files/doc-123.jpg',
        file_type: 'image',
        status: 'processing',
      },
    })
  }),

  http.get('http://localhost/api/documents', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: {
        items: [],
        pagination: { page: 1, size: 20, total: 0, has_next: false },
      },
    })
  }),

  http.get('http://localhost/api/documents/:id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: {
        id: params.id,
        title: '테스트 문서',
        category: 'lecture',
        capture_date: '2026-01-15T00:00:00.000Z',
        summary: '테스트 요약',
        tags: ['#CS-204'],
        key_concepts: ['개념1'],
        raw_text: '원문 텍스트',
        file_url: '/files/test.jpg',
        file_type: 'image',
        status: 'analyzed',
        deadline: null,
        created_at: '2026-01-15T00:00:00.000Z',
      },
    })
  }),

  http.patch('http://localhost/api/documents/:id', async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: { id: params.id, ...body },
    })
  }),

  http.delete('http://localhost/api/documents/:id', () => {
    return HttpResponse.json({ success: true, message: 'OK', data: null })
  }),

  // ─── Analysis ───────────────────────────────────────────────────────────────

  http.get('http://localhost/api/analysis/:id/status', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: {
        status: 'processing',
        started_at: '2026-01-15T00:00:00.000Z',
        finished_at: null,
      },
    })
  }),

  // ─── Search ─────────────────────────────────────────────────────────────────

  http.get('http://localhost/api/search/query', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: {
        mode_used: 'text',
        ai_available: false,
        items: [],
      },
    })
  }),

  http.get('http://localhost/api/search/status', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: { ai_available: false },
    })
  }),

  // ─── Graph (GraphQL) ────────────────────────────────────────────────────────

  http.post('http://localhost/api/graphql', () => {
    return HttpResponse.json({
      data: {
        nodes: [],
        edges: [],
        summary: { total: 0, by_category: {} },
      },
    })
  }),

  // ─── Calendar ───────────────────────────────────────────────────────────────

  http.get('http://localhost/api/calendar/events', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: { events: [] },
    })
  }),

  // ─── Tags ───────────────────────────────────────────────────────────────────

  http.get('http://localhost/api/tags', () => {
    return HttpResponse.json({
      success: true,
      message: 'OK',
      data: { items: [] },
    })
  }),
]
