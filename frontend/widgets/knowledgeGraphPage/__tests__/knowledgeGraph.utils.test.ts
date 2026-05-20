// FIRST:
//   Fast        — 순수 상수 조회, IO 없음
//   Independent — 각 테스트가 독립적
//   Repeatable  — 정적 매핑 테이블 기반
//   Self-Val.   — 테이블 매핑 정확성·알 수 없는 키 undefined 모두 expect()로 검증
//   Timely      — knowledgeGraph.utils.ts 매핑 테이블 확인 후 작성

import { describe, it, expect } from 'vitest'
import { CATEGORY_TO_NODE_CATEGORY } from '../knowledgeGraph.utils'

describe('CATEGORY_TO_NODE_CATEGORY', () => {
  it('단수 백엔드 카테고리를 올바르게 매핑한다', () => {
    expect(CATEGORY_TO_NODE_CATEGORY['lecture']).toBe('lecture')
    expect(CATEGORY_TO_NODE_CATEGORY['assignment']).toBe('assignment')
    expect(CATEGORY_TO_NODE_CATEGORY['notice']).toBe('notice')
    expect(CATEGORY_TO_NODE_CATEGORY['receipt']).toBe('receipt')
    expect(CATEGORY_TO_NODE_CATEGORY['memo']).toBe('memo')
  })

  it('복수/레거시 카테고리를 단수 NodeCategory로 매핑한다', () => {
    expect(CATEGORY_TO_NODE_CATEGORY['assignments']).toBe('assignment')
    expect(CATEGORY_TO_NODE_CATEGORY['exams']).toBe('exam')
    expect(CATEGORY_TO_NODE_CATEGORY['class_materials']).toBe('class')
    expect(CATEGORY_TO_NODE_CATEGORY['summaries']).toBe('summary')
    expect(CATEGORY_TO_NODE_CATEGORY['receipts']).toBe('receipt')
    expect(CATEGORY_TO_NODE_CATEGORY['notices']).toBe('notice')
  })

  it('매핑에 없는 키는 undefined를 반환한다', () => {
    expect(CATEGORY_TO_NODE_CATEGORY['unknown']).toBeUndefined()
    expect(CATEGORY_TO_NODE_CATEGORY['LECTURE']).toBeUndefined()
    expect(CATEGORY_TO_NODE_CATEGORY['']).toBeUndefined()
  })
})
