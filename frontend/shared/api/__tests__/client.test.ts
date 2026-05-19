// FIRST:
//   Fast        — MSW가 네트워크를 인터셉트하므로 실제 IO 없음
//   Independent — beforeEach에서 window.location.href 초기화,
//                 localStorage는 vitest.setup.ts의 afterEach에서 clear됨
//   Repeatable  — MSW 핸들러가 결정적 응답을 반환
//   Self-Val.   — 각 테스트가 expect()로 단언, 부작용(href, header)도 검증
//   Timely      — API 클라이언트 동작 확인 후 즉시 작성

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { server } from '../../../__mocks__/server'
import { http, HttpResponse } from 'msw'
import {
  ApiError,
  apiClient,
  apiFetchBlobUrl,
  getAccessToken,
  saveAccessToken,
  clearAccessToken,
} from '../client'

// Independent: 각 테스트 전에 이전 테스트의 부작용 초기화
beforeEach(() => {
  window.location.href = ''
  vi.clearAllMocks() // URL.createObjectURL 등 global mock 호출 이력 초기화
})

// ─── localStorage 유틸리티 ──────────────────────────────────────────────────

describe('getAccessToken / saveAccessToken / clearAccessToken', () => {
  it('저장한 토큰을 그대로 반환한다', () => {
    saveAccessToken('abc-123')
    expect(getAccessToken()).toBe('abc-123')
  })

  it('clearAccessToken 이후 null을 반환한다', () => {
    saveAccessToken('abc-123')
    clearAccessToken()
    expect(getAccessToken()).toBeNull()
  })

  it('토큰이 없으면 null을 반환한다', () => {
    expect(getAccessToken()).toBeNull()
  })
})

// ─── ApiError ─────────────────────────────────────────────────────────────────

describe('ApiError', () => {
  it('status와 message를 저장하고 name이 "ApiError"다', () => {
    const err = new ApiError(404, 'Not Found')
    expect(err.status).toBe(404)
    expect(err.message).toBe('Not Found')
    expect(err.name).toBe('ApiError')
  })

  it('Error를 상속하므로 instanceof Error가 true다', () => {
    expect(new ApiError(500, 'Error') instanceof Error).toBe(true)
  })

  it('errorCode를 선택적으로 저장한다', () => {
    const withCode = new ApiError(401, 'Unauthorized', 'INVALID_CREDENTIALS')
    const withoutCode = new ApiError(403, 'Forbidden')
    expect(withCode.errorCode).toBe('INVALID_CREDENTIALS')
    expect(withoutCode.errorCode).toBeUndefined()
  })
})

// ─── apiClient ────────────────────────────────────────────────────────────────

describe('apiClient', () => {
  it('200 응답을 ApiResponse<T> 형태로 반환한다', async () => {
    server.use(
      http.get('http://localhost/api/ping', () =>
        HttpResponse.json({ success: true, message: 'OK', data: { pong: true } }),
      ),
    )
    const res = await apiClient<{ pong: boolean }>('/ping')
    expect(res.data.pong).toBe(true)
  })

  it('4xx 응답에서 body의 message로 ApiError를 throw한다', async () => {
    server.use(
      http.get('http://localhost/api/not-found', () =>
        HttpResponse.json(
          { success: false, message: '리소스를 찾을 수 없습니다.', data: null },
          { status: 404 },
        ),
      ),
    )
    await expect(apiClient('/not-found')).rejects.toMatchObject({
      status: 404,
      message: '리소스를 찾을 수 없습니다.',
    })
  })

  it('requireAuth: true일 때 Authorization 헤더를 Bearer 토큰으로 설정한다', async () => {
    let capturedAuth: string | null = null
    server.use(
      http.get('http://localhost/api/protected', ({ request }) => {
        capturedAuth = request.headers.get('Authorization')
        return HttpResponse.json({ success: true, message: 'OK', data: {} })
      }),
    )
    saveAccessToken('my-token')
    await apiClient('/protected', { requireAuth: true })
    expect(capturedAuth).toBe('Bearer my-token')
  })

  it('requireAuth: true이고 토큰이 없으면 /login으로 리디렉션 후 ApiError(401)를 throw한다', async () => {
    // localStorage는 afterEach에서 clear되므로 토큰 없음 보장
    await expect(apiClient('/protected', { requireAuth: true })).rejects.toMatchObject({
      status: 401,
    })
    expect(window.location.href).toBe('/login')
  })

  it('Content-Type을 application/json으로 기본 설정한다', async () => {
    let capturedType: string | null = null
    server.use(
      http.post('http://localhost/api/json', ({ request }) => {
        capturedType = request.headers.get('Content-Type')
        return HttpResponse.json({ success: true, message: 'OK', data: {} })
      }),
    )
    await apiClient('/json', { method: 'POST', body: JSON.stringify({}) })
    expect(capturedType).toBe('application/json')
  })

  it('FormData body는 Content-Type을 강제 설정하지 않는다 (브라우저가 boundary 자동 처리)', async () => {
    let capturedType: string | null = null
    server.use(
      http.post('http://localhost/api/upload', ({ request }) => {
        capturedType = request.headers.get('Content-Type')
        return HttpResponse.json({ success: true, message: 'OK', data: {} })
      }),
    )
    const form = new FormData()
    form.append('file', new Blob(['data']), 'test.txt')
    saveAccessToken('tok')
    await apiClient('/upload', { method: 'POST', body: form, requireAuth: true })
    expect(capturedType).not.toBe('application/json')
  })

  it('서버가 401을 반환하면 토큰이 있어도 /login으로 리디렉션한다', async () => {
    server.use(
      http.get('http://localhost/api/session-expired', () =>
        HttpResponse.json(
          { success: false, message: 'Session expired', data: null },
          { status: 401 },
        ),
      ),
    )
    saveAccessToken('valid-token')
    await expect(
      apiClient('/session-expired', { requireAuth: true }),
    ).rejects.toMatchObject({ status: 401, message: 'Unauthorized' })
    expect(window.location.href).toBe('/login')
  })

  it('성공(2xx) 응답이지만 body가 없으면 ApiError(500, "Empty response")를 throw한다', async () => {
    server.use(
      http.post('http://localhost/api/no-body', () => new HttpResponse(null, { status: 204 })),
    )
    await expect(apiClient('/no-body', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      status: 500,
      message: 'Empty response',
    })
  })

  it('오류 응답의 body가 없으면 statusText를 message로 사용한다', async () => {
    server.use(
      http.delete('http://localhost/api/resource', () =>
        new HttpResponse(null, { status: 503, statusText: 'Service Unavailable' }),
      ),
    )
    await expect(apiClient('/resource', { method: 'DELETE' })).rejects.toMatchObject({
      status: 503,
      message: 'Service Unavailable',
    })
  })

  it('오류 응답의 error_code가 ApiError.errorCode에 매핑된다', async () => {
    server.use(
      http.post('http://localhost/api/restricted', () =>
        HttpResponse.json(
          {
            success: false,
            message: '권한이 없습니다.',
            data: null,
            error_code: 'PERMISSION_DENIED',
          },
          { status: 403 },
        ),
      ),
    )
    await expect(
      apiClient('/restricted', { method: 'POST', body: '{}' }),
    ).rejects.toMatchObject({
      status: 403,
      message: '권한이 없습니다.',
      errorCode: 'PERMISSION_DENIED',
    })
  })

  it('requireAuth가 false(기본값)이면 토큰이 있어도 Authorization 헤더를 추가하지 않는다', async () => {
    let capturedAuth: string | null = null
    server.use(
      http.get('http://localhost/api/public', ({ request }) => {
        capturedAuth = request.headers.get('Authorization')
        return HttpResponse.json({ success: true, message: 'OK', data: {} })
      }),
    )
    saveAccessToken('should-not-appear')
    await apiClient('/public')
    expect(capturedAuth).toBeNull()
  })
})

// ─── apiFetchBlobUrl ──────────────────────────────────────────────────────────

describe('apiFetchBlobUrl', () => {
  it('blob 응답을 URL.createObjectURL에 전달하고 결과 URL을 반환한다', async () => {
    server.use(
      http.get('http://localhost/api/files/img', () =>
        new HttpResponse(new Uint8Array([0xff, 0xd8, 0xff]), {
          headers: { 'Content-Type': 'image/jpeg' },
        }),
      ),
    )
    saveAccessToken('tok')
    const result = await apiFetchBlobUrl('/files/img')
    expect(URL.createObjectURL).toHaveBeenCalledOnce()
    expect(result).toBe('blob:mock-url') // vitest.setup.ts의 mock 반환값
  })

  it('토큰이 있으면 Authorization 헤더를 설정한다', async () => {
    let capturedAuth: string | null = null
    server.use(
      http.get('http://localhost/api/files/doc', ({ request }) => {
        capturedAuth = request.headers.get('Authorization')
        return new HttpResponse(new Uint8Array([1]), {
          headers: { 'Content-Type': 'application/octet-stream' },
        })
      }),
    )
    saveAccessToken('blob-token')
    await apiFetchBlobUrl('/files/doc')
    expect(capturedAuth).toBe('Bearer blob-token')
  })

  it('토큰이 없으면 Authorization 헤더 없이 요청한다', async () => {
    let capturedAuth: string | null = null
    server.use(
      http.get('http://localhost/api/files/public', ({ request }) => {
        capturedAuth = request.headers.get('Authorization')
        return new HttpResponse(new Uint8Array([1]), {
          headers: { 'Content-Type': 'image/png' },
        })
      }),
    )
    // localStorage는 afterEach에서 clear되므로 토큰 없음 보장
    await apiFetchBlobUrl('/files/public')
    expect(capturedAuth).toBeNull()
  })

  it('401 응답에서 /login으로 리디렉션 후 ApiError(401)를 throw한다', async () => {
    server.use(
      http.get('http://localhost/api/files/secret', () =>
        new HttpResponse(null, { status: 401 }),
      ),
    )
    await expect(apiFetchBlobUrl('/files/secret')).rejects.toMatchObject({
      status: 401,
      message: 'Unauthorized',
    })
    expect(window.location.href).toBe('/login')
  })

  it('401이 아닌 오류 응답에서 ApiError(status, statusText)를 throw한다', async () => {
    server.use(
      http.get('http://localhost/api/files/missing', () =>
        new HttpResponse(null, { status: 404, statusText: 'Not Found' }),
      ),
    )
    await expect(apiFetchBlobUrl('/files/missing')).rejects.toMatchObject({
      status: 404,
      message: 'Not Found',
    })
  })
})
