import { vi } from 'vitest'

export const mockPush = vi.fn()
export const mockBack = vi.fn()
export const mockReplace = vi.fn()
export const mockRefresh = vi.fn()

export const useRouter = vi.fn(() => ({
  push: mockPush,
  back: mockBack,
  forward: vi.fn(),
  replace: mockReplace,
  refresh: mockRefresh,
  prefetch: vi.fn(),
}))

export const usePathname = vi.fn(() => '/')
export const useSearchParams = vi.fn(() => new URLSearchParams())
export const useParams = vi.fn(() => ({ id: 'test-id' }))
