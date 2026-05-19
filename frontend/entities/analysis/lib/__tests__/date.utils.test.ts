// FIRST:
//   Fast        — 네트워크·DOM 없음, 순수 함수 호출만
//   Independent — 입력이 고정값이므로 테스트 간 공유 상태 없음
//   Repeatable  — UTC 기준 고정 날짜 → 타임존 무관하게 동일 결과
//   Self-Val.   — 모든 케이스 expect()로 단언, console.log 없음
//   Timely      — 실제 코드 검토 직후 작성

import { describe, it, expect } from 'vitest'
import { isoToDisplay, displayToIso } from '../date.utils'

describe('isoToDisplay', () => {
  it('null을 빈 문자열로 반환한다', () => {
    expect(isoToDisplay(null)).toBe('')
  })

  it('빈 문자열을 빈 문자열로 반환한다', () => {
    expect(isoToDisplay('')).toBe('')
  })

  it('파싱 불가능한 문자열을 빈 문자열로 반환한다', () => {
    expect(isoToDisplay('not-a-date')).toBe('')
  })

  it('정상 ISO8601을 MM/DD/YYYY 형식으로 변환한다', () => {
    expect(isoToDisplay('2026-01-15T00:00:00.000Z')).toBe('01/15/2026')
  })

  it('UTC 기준으로 처리하여 타임존에 무관한 결과를 반환한다', () => {
    // 2026-03-01T23:00:00.000Z → UTC 기준 날짜는 3월 1일
    expect(isoToDisplay('2026-03-01T23:00:00.000Z')).toBe('03/01/2026')
  })

  it('한 자리 월·일을 2자리로 패딩한다', () => {
    expect(isoToDisplay('2026-05-07T00:00:00.000Z')).toBe('05/07/2026')
  })
})

describe('displayToIso', () => {
  it('MM/DD/YYYY를 UTC 자정 ISO8601로 변환한다', () => {
    expect(displayToIso('01/15/2026')).toBe('2026-01-15T00:00:00.000Z')
  })

  it('구분자가 /가 아니면 원문을 반환한다', () => {
    expect(displayToIso('2026-01-15')).toBe('2026-01-15')
  })

  it('부분이 3개가 아니면 원문을 반환한다', () => {
    expect(displayToIso('01/2026')).toBe('01/2026')
    expect(displayToIso('')).toBe('')
  })

  it('날짜 범위를 벗어난 값이면 원문을 반환한다', () => {
    expect(displayToIso('13/40/2026')).toBe('13/40/2026')
  })

  it('isoToDisplay의 역함수로 동작한다 (round-trip)', () => {
    const original = '2026-05-07T00:00:00.000Z'
    expect(displayToIso(isoToDisplay(original))).toBe(original)
  })
})
