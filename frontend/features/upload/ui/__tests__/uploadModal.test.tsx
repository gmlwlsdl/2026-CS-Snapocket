// FIRST:
//   Fast        — 렌더링만, 네트워크 없음
//   Independent — vi.fn() 핸들러로 각 테스트 독립
//   Repeatable  — 결정적 props 기반
//   Self-Val.   — 렌더링·이벤트 호출·파일명 표시 모두 expect()로 검증
//   Timely      — uploadModal.tsx의 open/onClose/onUpload 분기 확인 후 작성

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UploadModal } from '../uploadModal'

function makeFile(name = 'test.pdf') {
  return new File(['content'], name, { type: 'application/pdf' })
}

describe('UploadModal', () => {
  it('open=false이면 아무것도 렌더링하지 않는다', () => {
    const { container } = render(
      <UploadModal open={false} onClose={vi.fn()} onUpload={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('open=true이면 모달 제목과 버튼이 렌더링된다', () => {
    render(<UploadModal open={true} onClose={vi.fn()} onUpload={vi.fn()} />)

    expect(screen.getByText('파일 업로드')).toBeDefined()
    expect(screen.getByText('분석 시작')).toBeDefined()
    expect(screen.getByText('취소')).toBeDefined()
  })

  it('오버레이(배경) 클릭 시 onClose가 호출된다', () => {
    const onClose = vi.fn()
    const { container } = render(
      <UploadModal open={true} onClose={onClose} onUpload={vi.fn()} />,
    )

    // 최외곽 overlay div 클릭
    const overlay = container.firstChild as HTMLElement
    fireEvent.click(overlay)

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('취소 버튼 클릭 시 onClose가 호출되고 onUpload는 호출되지 않는다', () => {
    const onClose = vi.fn()
    const onUpload = vi.fn()
    render(<UploadModal open={true} onClose={onClose} onUpload={onUpload} />)

    fireEvent.click(screen.getByText('취소'))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('Close 버튼 클릭 시 onClose가 호출된다', () => {
    const onClose = vi.fn()
    render(<UploadModal open={true} onClose={onClose} onUpload={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Close modal' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('파일 input onChange 이벤트 시 선택 파일명이 드롭존에 표시된다', () => {
    render(<UploadModal open={true} onClose={vi.fn()} onUpload={vi.fn()} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement

    Object.defineProperty(input, 'files', {
      value: [makeFile('lecture_note.pdf')],
      configurable: true,
    })
    fireEvent.change(input)

    expect(screen.getByText('lecture_note.pdf')).toBeDefined()
  })

  it('파일 없이 "분석 시작" 클릭 시 기본 파일(sample_document.pdf)로 onUpload를 호출한다', () => {
    const onUpload = vi.fn()
    render(<UploadModal open={true} onClose={vi.fn()} onUpload={onUpload} />)

    fireEvent.click(screen.getByText('분석 시작'))

    expect(onUpload).toHaveBeenCalledTimes(1)
    const calledFile: File = onUpload.mock.calls[0][0]
    expect(calledFile.name).toBe('sample_document.pdf')
  })

  it('파일 선택 후 "분석 시작" 클릭 시 선택된 파일로 onUpload를 호출한다', () => {
    const onUpload = vi.fn()
    render(<UploadModal open={true} onClose={vi.fn()} onUpload={onUpload} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeFile('slide.jpg')

    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    fireEvent.change(input)

    fireEvent.click(screen.getByText('분석 시작'))

    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it('"분석 시작" 클릭 후 onClose가 호출되어 모달이 닫힌다', () => {
    const onClose = vi.fn()
    render(<UploadModal open={true} onClose={onClose} onUpload={vi.fn()} />)

    fireEvent.click(screen.getByText('분석 시작'))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
