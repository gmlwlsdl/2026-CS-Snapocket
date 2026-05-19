// FIRST:
//   Fast        — hover/unhover는 동기적 상태 변경, API는 MSW 즉시 응답
//   Independent — beforeEach에서 vi.clearAllMocks() + pathname 기본값 복원
//   Repeatable  — MSW 핸들러가 결정적 유저 데이터 반환
//   Self-Val.   — style·text·aria 속성 모두 expect()로 단언
//   Timely      — SidebarNav 구조(hover, getMe, pathname) 확인 후 즉시 작성

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { server } from '../../../__mocks__/server'
import { http, HttpResponse } from 'msw'
import { SidebarNav } from '../sidebarNav'
import { usePathname } from 'next/navigation'

// Independent: 각 테스트 전에 mock 상태 초기화
beforeEach(() => {
  vi.clearAllMocks()
  // usePathname 기본 반환값 복원 (__mocks__/next/navigation.ts의 기본값)
  vi.mocked(usePathname).mockReturnValue('/')
})

describe('SidebarNav', () => {
  // ─── 레이아웃 ──────────────────────────────────────────────────────────────

  it('초기 렌더링 시 width가 81(px)이다', () => {
    render(<SidebarNav />)
    const aside = screen.getByRole('complementary')
    expect(aside).toHaveStyle({ width: '81px' })
  })

  it('마우스 진입 시 width가 256(px)으로 확장된다', async () => {
    const user = userEvent.setup()
    render(<SidebarNav />)

    await user.hover(screen.getByRole('complementary'))
    expect(screen.getByRole('complementary')).toHaveStyle({ width: '256px' })
  })

  it('마우스 이탈 시 width가 81(px)으로 축소된다', async () => {
    const user = userEvent.setup()
    render(<SidebarNav />)

    const aside = screen.getByRole('complementary')
    await user.hover(aside)
    await user.unhover(aside)
    expect(aside).toHaveStyle({ width: '81px' })
  })

  // ─── 활성 라우트 스타일 ─────────────────────────────────────────────────────

  it('"/" 경로에서 Graph View 링크가 활성 border-left 스타일을 가진다', () => {
    vi.mocked(usePathname).mockReturnValue('/')
    render(<SidebarNav />)

    const graphLink = screen.getByRole('link', { name: /graph view/i })
    expect(graphLink).toHaveStyle({ borderLeft: '2px solid #81ecff' })
  })

  it('"/calendar" 경로에서 Calendar 링크가 활성 border-left 스타일을 가진다', () => {
    vi.mocked(usePathname).mockReturnValue('/calendar')
    render(<SidebarNav />)

    const calendarLink = screen.getByRole('link', { name: /calendar/i })
    expect(calendarLink).toHaveStyle({ borderLeft: '2px solid #81ecff' })
  })

  it('"/calendar" 경로에서 Graph View 링크는 활성 색상 border-left가 아니다', () => {
    vi.mocked(usePathname).mockReturnValue('/calendar')
    render(<SidebarNav />)

    const graphLink = screen.getByRole('link', { name: /graph view/i })
    // jsdom에서 transparent → rgba(0,0,0,0)으로 정규화되므로 부재 확인이 더 안정적
    expect(graphLink).not.toHaveStyle({ borderLeft: '2px solid #81ecff' })
  })

  // ─── 업로드 버튼 ────────────────────────────────────────────────────────────

  it('onUpload prop이 주어지면 버튼 클릭 시 호출된다', async () => {
    const handleUpload = vi.fn()
    const user = userEvent.setup()
    render(<SidebarNav onUpload={handleUpload} />)

    await user.click(screen.getByRole('button', { name: /upload new file/i }))
    expect(handleUpload).toHaveBeenCalledTimes(1)
  })

  // ─── 유저 프로필 ────────────────────────────────────────────────────────────

  it('getMe() 성공 시 API에서 받은 이름과 이메일을 표시한다', async () => {
    localStorage.setItem('access_token', 'mock-token')
    render(<SidebarNav />)

    // handlers.ts 기본 /api/auth/me 응답: name='테스트 유저', email='test@example.com'
    await waitFor(() =>
      expect(screen.getByText('테스트 유저')).toBeInTheDocument(),
    )
    expect(screen.getByText('test@example.com')).toBeInTheDocument()
  })

  it('getMe() 실패 시 fallback 이름·이메일을 표시한다', async () => {
    server.use(
      http.get('http://localhost/api/auth/me', () =>
        HttpResponse.json(
          { success: false, message: 'Unauthorized', data: null },
          { status: 401 },
        ),
      ),
    )
    render(<SidebarNav />)

    // getMe()가 throw → catch → setUser(null) → fallback 값 표시
    await waitFor(() =>
      expect(screen.getByText('김스냅')).toBeInTheDocument(),
    )
    expect(screen.getByText('kimsnap@gmail.com')).toBeInTheDocument()
  })
})
