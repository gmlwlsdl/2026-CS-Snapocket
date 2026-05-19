// FIRST:
//   Fast        — 실제 파일 IO 없음, MSW가 네트워크를 인메모리에서 처리
//   Independent — beforeEach에서 인증 토큰 설정, afterEach에서 MSW·localStorage 자동 초기화
//   Repeatable  — 고정 mock 파일 + 결정적 MSW 응답
//   Self-Val.   — 반환값·요청 payload·URL 파라미터까지 모두 expect()로 검증
//   Timely      — document.api.ts 시그니처 확인 후 즉시 작성

import { describe, it, expect, beforeEach } from 'vitest'
import { server } from '../../../__mocks__/server'
import { http, HttpResponse } from 'msw'
import {
  uploadDocument,
  fetchDocuments,
  fetchDocument,
  deleteDocument,
  updateDocument,
} from '../api/document.api'
import { ApiError } from '@/shared/api'

const TOKEN = 'doc-test-token'

// Independent: 각 테스트는 동일한 인증 상태에서 시작
beforeEach(() => {
  localStorage.setItem('access_token', TOKEN)
})

// ─── uploadDocument ───────────────────────────────────────────────────────────

describe('uploadDocument', () => {
  it('파일 업로드 성공 시 UploadResponse를 반환한다', async () => {
    const file = new File(['content'], 'note.jpg', { type: 'image/jpeg' })
    const result = await uploadDocument(file)

    expect(result.document_id).toBe('doc-123')
    expect(result.status).toBe('processing')
    expect(result.file_type).toBe('image')
  })

  it('FormData에 file과 autoAnalyze 값을 append한다', async () => {
    // Fast: request 네트워크 본문 파싱 대신 FormData.prototype.append를 spy해 직접 검증
    // Repeatable: jsdom FormData를 msw/node에서 text()로 읽으면 타임아웃 발생하므로
    //             소스 레벨 spy가 더 안정적
    const appendSpy = vi.spyOn(FormData.prototype, 'append')

    const file = new File(['data'], 'slide.jpg', { type: 'image/jpeg' })
    await uploadDocument(file, false)

    expect(appendSpy).toHaveBeenCalledWith('file', file)
    expect(appendSpy).toHaveBeenCalledWith('autoAnalyze', 'false')

    appendSpy.mockRestore()
  })

  it('Content-Type을 application/json으로 강제 설정하지 않는다', async () => {
    let capturedType: string | null = null
    server.use(
      http.post('http://localhost/api/documents/upload', ({ request }) => {
        capturedType = request.headers.get('Content-Type')
        return HttpResponse.json({
          success: true,
          message: 'OK',
          data: { document_id: 'y', file_url: '/y', file_type: 'image', status: 'uploaded' },
        })
      }),
    )

    await uploadDocument(new File([''], 'a.jpg', { type: 'image/jpeg' }))
    expect(capturedType).not.toBe('application/json')
  })

  it('서버가 422를 반환하면 ApiError를 throw한다', async () => {
    server.use(
      http.post('http://localhost/api/documents/upload', () =>
        HttpResponse.json(
          { success: false, message: '지원하지 않는 파일 형식입니다.', data: null },
          { status: 422 },
        ),
      ),
    )

    const file = new File([''], 'video.mp4', { type: 'video/mp4' })
    await expect(uploadDocument(file)).rejects.toBeInstanceOf(ApiError)
    await expect(uploadDocument(file)).rejects.toMatchObject({
      status: 422,
      message: '지원하지 않는 파일 형식입니다.',
    })
  })
})

// ─── fetchDocuments ───────────────────────────────────────────────────────────

describe('fetchDocuments', () => {
  it('파라미터 없이 호출하면 items와 pagination을 반환한다', async () => {
    const result = await fetchDocuments()

    expect(result.items).toEqual([])
    expect(result.pagination).toMatchObject({ page: 1, size: 20, total: 0 })
  })

  it('쿼리 파라미터를 URL에 올바르게 직렬화한다', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost/api/documents', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({
          success: true,
          message: 'OK',
          data: { items: [], pagination: { page: 2, size: 10, total: 0, has_next: false } },
        })
      }),
    )

    await fetchDocuments({ page: 2, size: 10, category: 'lecture' })

    expect(capturedUrl).toContain('page=2')
    expect(capturedUrl).toContain('size=10')
    expect(capturedUrl).toContain('category=lecture')
  })

  it('undefined 파라미터는 URL에 포함하지 않는다', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost/api/documents', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({
          success: true,
          message: 'OK',
          data: { items: [], pagination: { page: 1, size: 20, total: 0, has_next: false } },
        })
      }),
    )

    await fetchDocuments({ page: 1, category: undefined })

    expect(capturedUrl).toContain('page=1')
    expect(capturedUrl).not.toContain('category')
  })
})

// ─── fetchDocument ────────────────────────────────────────────────────────────

describe('fetchDocument', () => {
  it('ID로 DocumentDetail을 반환한다', async () => {
    const result = await fetchDocument('doc-abc')

    expect(result.id).toBe('doc-abc')
    expect(result.status).toBe('analyzed')
    expect(result.category).toBe('lecture')
  })
})

// ─── updateDocument ───────────────────────────────────────────────────────────

describe('updateDocument', () => {
  it('PATCH 요청을 보내고 업데이트된 DocumentDetail을 반환한다', async () => {
    server.use(
      http.patch('http://localhost/api/documents/:id', async ({ request, params }) => {
        const body = await request.json() as Record<string, unknown>
        return HttpResponse.json({
          success: true,
          message: 'OK',
          data: {
            id: params.id,
            title: body['title'] as string,
            category: 'lecture',
            capture_date: null,
            summary: '',
            tags: [],
            key_concepts: [],
            raw_text: '',
            file_url: '/f',
            file_type: 'image',
            status: 'analyzed',
            deadline: null,
            created_at: '2026-01-01T00:00:00.000Z',
          },
        })
      }),
    )

    const result = await updateDocument('doc-abc', { title: '수정된 제목' })
    expect(result.title).toBe('수정된 제목')
    expect(result.id).toBe('doc-abc')
  })
})

// ─── deleteDocument ───────────────────────────────────────────────────────────

describe('deleteDocument', () => {
  it('DELETE 요청을 전송하고 void(undefined)를 반환한다', async () => {
    let deleteCalled = false
    server.use(
      http.delete('http://localhost/api/documents/:id', ({ params }) => {
        deleteCalled = true
        expect(params.id).toBe('to-delete')
        return HttpResponse.json({ success: true, message: 'OK', data: null })
      }),
    )

    const result = await deleteDocument('to-delete')
    expect(result).toBeUndefined()
    expect(deleteCalled).toBe(true)
  })
})
