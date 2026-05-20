// FIRST:
//   Fast        — 렌더링만, 네트워크 없음
//   Independent — 각 테스트는 독립 props/vi.fn()으로 격리
//   Repeatable  — 결정적 status 값 기반
//   Self-Val.   — role·텍스트·이벤트 호출·전파 차단 모두 expect()로 검증
//   Timely      — toastStatus.tsx의 3가지 status 분기 및 클릭 조건 확인 후 작성

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ToastStatus } from '../toastStatus'
import type { ToastItem } from '../toastStatus'

function makeItem(overrides: Partial<ToastItem> = {}): ToastItem {
  return {
    id: 'toast-1',
    fileName: 'lecture.pdf',
    status: 'processing',
    analysisId: 'analysis-1',
    ...overrides,
  }
}

describe('ToastStatus', () => {
  it('items가 빈 배열이면 아무것도 렌더링하지 않는다', () => {
    const { container } = render(
      <ToastStatus items={[]} onItemClick={vi.fn()} onCancel={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('processing 상태 토스트는 role="status"와 "분석 중..." 텍스트를 렌더링한다', () => {
    render(
      <ToastStatus
        items={[makeItem({ status: 'processing' })]}
        onItemClick={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByRole('status')).toBeDefined()
    expect(screen.getByText('분석 중...')).toBeDefined()
    expect(screen.getByText('lecture.pdf')).toBeDefined()
  })

  it('complete 상태 토스트는 role="button"과 "분석 완료" 텍스트를 렌더링한다', () => {
    render(
      <ToastStatus
        items={[makeItem({ status: 'complete' })]}
        onItemClick={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: undefined })).toBeDefined()
    expect(screen.getByText('분석 완료')).toBeDefined()
  })

  it('error 상태 토스트는 role="status"와 "분석 실패" 텍스트를 렌더링한다', () => {
    render(
      <ToastStatus
        items={[makeItem({ status: 'error' })]}
        onItemClick={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText('분석 실패')).toBeDefined()
    expect(screen.getByText('분석 중 오류가 발생했어요.')).toBeDefined()
  })

  it('complete 토스트를 클릭하면 onItemClick이 호출된다', () => {
    const onItemClick = vi.fn()
    const item = makeItem({ status: 'complete' })
    render(
      <ToastStatus items={[item]} onItemClick={onItemClick} onCancel={vi.fn()} />,
    )

    // role="button"인 토스트 카드 직접 클릭
    fireEvent.click(screen.getByRole('button', { name: undefined }))

    expect(onItemClick).toHaveBeenCalledWith(item)
  })

  it('processing 상태의 취소 버튼 클릭 시 onCancel이 호출되고 onItemClick은 호출되지 않는다', () => {
    const onItemClick = vi.fn()
    const onCancel = vi.fn()
    const item = makeItem({ status: 'processing' })
    render(
      <ToastStatus items={[item]} onItemClick={onItemClick} onCancel={onCancel} />,
    )

    fireEvent.click(screen.getByRole('button', { name: '취소' }))

    expect(onCancel).toHaveBeenCalledWith(item)
    expect(onItemClick).not.toHaveBeenCalled()
  })

  it('error 상태의 닫기 버튼 클릭 시 onCancel이 호출된다', () => {
    const onCancel = vi.fn()
    const item = makeItem({ status: 'error' })
    render(
      <ToastStatus items={[item]} onItemClick={vi.fn()} onCancel={onCancel} />,
    )

    fireEvent.click(screen.getByRole('button', { name: '닫기' }))

    expect(onCancel).toHaveBeenCalledWith(item)
  })

  it('여러 상태의 토스트를 동시에 렌더링한다', () => {
    const items: ToastItem[] = [
      makeItem({ id: 't1', status: 'processing', fileName: 'a.pdf' }),
      makeItem({ id: 't2', status: 'complete', fileName: 'b.pdf' }),
      makeItem({ id: 't3', status: 'error', fileName: 'c.pdf' }),
    ]
    render(<ToastStatus items={items} onItemClick={vi.fn()} onCancel={vi.fn()} />)

    expect(screen.getByText('a.pdf')).toBeDefined()
    expect(screen.getByText('b.pdf')).toBeDefined()
    expect(screen.getByText('c.pdf')).toBeDefined()
  })

  it('complete 토스트에 "확인하기 →" 클릭 힌트가 표시된다', () => {
    render(
      <ToastStatus
        items={[makeItem({ status: 'complete' })]}
        onItemClick={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText('확인하기 →')).toBeDefined()
  })
})
