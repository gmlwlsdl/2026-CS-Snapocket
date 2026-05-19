// FIRST:
//   Fast        — MSW 즉시 응답, 인위적 지연 없음
//   Independent — beforeEach에서 vi.clearAllMocks()로 router mock 초기화,
//                 각 테스트가 독립적으로 render
//   Repeatable  — MSW로 결정적 네트워크 응답 보장
//   Self-Val.   — expect()로 UI 상태·라우팅 모두 단언
//   Timely      — 컴포넌트 구조 파악 직후 작성

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { server } from '../../../../__mocks__/server'
import { http, HttpResponse } from 'msw'
import { LoginForm } from '../loginForm'
import { useRouter } from 'next/navigation'

const mockPush = vi.fn()

// Independent: 각 테스트 전에 mock 호출 이력 초기화
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useRouter).mockReturnValue({
    push: mockPush,
    back: vi.fn(),
    forward: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })
})

describe('LoginForm', () => {
  it('이메일·비밀번호 입력 필드와 제출 버튼을 렌더링한다', () => {
    render(<LoginForm />)
    expect(screen.getByLabelText('Email Address')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
  })

  it('올바른 자격증명으로 제출하면 "/"로 라우팅한다', async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    await user.type(screen.getByLabelText('Email Address'), 'test@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/'))
    expect(mockPush).toHaveBeenCalledTimes(1)
  })

  it('제출 중에는 버튼이 "Signing in…"으로 변경되고 disabled 상태다', async () => {
    server.use(
      http.post('http://localhost/api/auth/login', async () => {
        await new Promise((r) => setTimeout(r, 50))
        return HttpResponse.json({
          success: true,
          message: 'OK',
          data: { access_token: 'tok', token_type: 'Bearer' },
        })
      }),
    )
    const user = userEvent.setup()
    render(<LoginForm />)

    await user.type(screen.getByLabelText('Email Address'), 'test@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    // Independent: click을 await하지 않고 로딩 상태를 즉시 확인
    user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled(),
    )
    // 비동기 제출이 완전히 끝날 때까지 대기 → 다음 테스트로 상태 누수 방지
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/'), { timeout: 2000 })
  })

  it('잘못된 자격증명이면 role="alert" 에러 메시지를 표시한다', async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    await user.type(screen.getByLabelText('Email Address'), 'wrong@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    // handlers.ts의 기본 401 응답 메시지
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        '이메일 또는 비밀번호가 올바르지 않습니다.',
      ),
    )
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('네트워크 오류 시 일반 에러 메시지를 표시한다', async () => {
    server.use(http.post('http://localhost/api/auth/login', () => HttpResponse.error()))
    const user = userEvent.setup()
    render(<LoginForm />)

    await user.type(screen.getByLabelText('Email Address'), 'test@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        '로그인에 실패했습니다. 다시 시도해주세요.',
      ),
    )
  })

  it('비밀번호 표시 토글이 input type을 password ↔ text로 전환한다', async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    const passwordInput = screen.getByLabelText('Password')
    expect(passwordInput).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(passwordInput).toHaveAttribute('type', 'text')

    await user.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('입력값 변경 시 이전 에러 메시지가 사라진다', async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    // 먼저 에러 상태 만들기
    await user.type(screen.getByLabelText('Email Address'), 'wrong@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())

    // 입력 변경 → 에러 제거
    await user.type(screen.getByLabelText('Email Address'), 'a')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
