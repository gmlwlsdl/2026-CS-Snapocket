// FIRST:
//   Fast        — 순수 함수, 네트워크·IO 없음
//   Independent — 각 테스트가 독립적, 부작용 없음
//   Repeatable  — 결정적 dictionary 기반
//   Self-Val.   — 반환값·key 집합·non-empty 모두 expect()로 검증
//   Timely      — i18n/index.ts의 dictionary 타입 확인 후 작성

import { describe, it, expect } from 'vitest'
import { t } from '../index'

describe('t (번역 함수)', () => {
  it("기본 lang='ko'로 한국어 문자열을 반환한다", () => {
    expect(t('analysisDetail')).toBe('분석 상세')
    expect(t('back')).toBe('뒤로 가기')
  })

  it("lang='en'으로 영어 문자열을 반환한다", () => {
    expect(t('analysisDetail', 'en')).toBe('Analysis Detail')
    expect(t('back', 'en')).toBe('Back')
  })

  it('같은 key라도 lang에 따라 다른 문자열을 반환한다', () => {
    expect(t('analyzing', 'ko')).not.toBe(t('analyzing', 'en'))
  })

  it('ko dictionary의 모든 값이 non-empty string이다', () => {
    const koKeys: Parameters<typeof t>[0][] = [
      'analysisDetail', 'confirmSave', 'analysisComplete', 'analyzing', 'analysisFailed',
      'saving', 'editingExtractedData', 'back', 'documentTitle', 'category', 'captureDate',
      'contentSummary', 'aiGenerated', 'tags', 'addTag', 'discardExtraction', 'discarding',
      'recalibrateAiLens', 'askAiAboutKnowledgeGraph', 'clickToView', 'uploadSources',
      'feedYourKnowledgeVault', 'supportForPdfJpgPngOrMp4', 'selectFiles', 'cancel',
      'startAnalysis', 'dropFilesHereOrClickToBrowse', 'findDocument', 'deadline',
      'keyConcepts', 'rawText',
    ]

    for (const key of koKeys) {
      const value = t(key, 'ko')
      expect(value, `ko.${key}가 비어 있음`).toBeTruthy()
      expect(typeof value).toBe('string')
    }
  })

  it('en dictionary의 모든 값이 non-empty string이다', () => {
    const enKeys: Parameters<typeof t>[0][] = [
      'analysisDetail', 'confirmSave', 'analysisComplete', 'analyzing', 'analysisFailed',
      'saving', 'editingExtractedData', 'back', 'documentTitle', 'category', 'captureDate',
      'contentSummary', 'aiGenerated', 'tags', 'addTag', 'discardExtraction', 'discarding',
      'recalibrateAiLens', 'askAiAboutKnowledgeGraph', 'clickToView', 'uploadSources',
      'feedYourKnowledgeVault', 'supportForPdfJpgPngOrMp4', 'selectFiles', 'cancel',
      'startAnalysis', 'dropFilesHereOrClickToBrowse', 'findDocument', 'deadline',
      'keyConcepts', 'rawText',
    ]

    for (const key of enKeys) {
      const value = t(key, 'en')
      expect(value, `en.${key}가 비어 있음`).toBeTruthy()
      expect(typeof value).toBe('string')
    }
  })
})
