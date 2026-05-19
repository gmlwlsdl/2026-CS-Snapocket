import '@testing-library/jest-dom/vitest'
import { beforeAll, afterEach, afterAll, vi } from 'vitest'
import { server } from './__mocks__/server'

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' })

  // MSW v2의 server.listen()은 global.fetch를 자신의 인터셉터로 교체한다.
  // client.ts의 BASE_URL="/api"는 상대 경로 → Node.js fetch는 base origin 없이는 실패.
  // server.listen() 이후에 래퍼를 등록해야 MSW 인터셉터 위에서 동작한다.
  const mswFetch = global.fetch
  global.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === 'string' && input.startsWith('/')) {
      return mswFetch(`http://localhost${input}`, init)
    }
    return mswFetch(input, init)
  }
})

afterEach(() => {
  server.resetHandlers()
  localStorage.clear()
})

afterAll(() => {
  server.close()
})

// client.ts의 redirectToLogin()이 window.location.href를 변경하므로
// jsdom의 읽기 전용 location을 writable로 override
Object.defineProperty(window, 'location', {
  value: {
    href: '',
    assign: vi.fn(),
    replace: vi.fn(),
    reload: vi.fn(),
  },
  writable: true,
})

// apiFetchBlobUrl에서 사용하는 Blob URL API mock
global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
global.URL.revokeObjectURL = vi.fn()

// react-force-graph-2d가 Canvas API를 직접 호출할 경우를 대비한 최소 mock
HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
  clearRect: vi.fn(),
  fillRect: vi.fn(),
  beginPath: vi.fn(),
  arc: vi.fn(),
  fill: vi.fn(),
  stroke: vi.fn(),
  createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
  save: vi.fn(),
  restore: vi.fn(),
  scale: vi.fn(),
  translate: vi.fn(),
  drawImage: vi.fn(),
  measureText: vi.fn(() => ({ width: 0 })),
  fillText: vi.fn(),
})) as unknown as typeof HTMLCanvasElement.prototype.getContext
