'use client'

import { t as translate } from '@/shared/lib/i18n'

interface AiInputBarProps {
  value: string
  aiAvailable: boolean
  modeUsed?: 'text' | 'semantic' | null
  isSearching?: boolean
  onValueChange: (value: string) => void
  onSubmitSearch: () => void
}

export function AiInputBar({
  value,
  aiAvailable,
  modeUsed,
  isSearching = false,
  onValueChange,
  onSubmitSearch,
}: AiInputBarProps) {
  const statusLabel = isSearching
    ? '검색 중'
    : aiAvailable
      ? modeUsed === 'semantic'
        ? 'AI 임베딩 검색'
        : '텍스트 검색 + AI 대기'
      : '텍스트 검색만 가능'

  return (
    <div className="absolute bottom-8 left-1/2 z-10 w-[672px] -translate-x-1/2">
      <div className="mb-2 flex justify-center">
        <span
          className="rounded-full px-3 py-1 text-xs"
          style={{
            background: aiAvailable ? 'rgba(129,236,255,0.16)' : 'rgba(170,171,175,0.16)',
            color: aiAvailable ? '#b9f8ff' : '#d2d5da',
            border: aiAvailable ? '1px solid rgba(129,236,255,0.28)' : '1px solid rgba(170,171,175,0.2)',
          }}
        >
          {statusLabel}
        </span>
      </div>
      <div
        className="flex h-14 items-center gap-3 px-6"
        style={{
          background: 'rgba(23,26,29,0.7)',
          border: '1px solid rgba(70,72,75,0.15)',
          borderRadius: 9999,
          backdropFilter: 'blur(12px)',
        }}
      >
        <img src="/ai.svg" alt="AI 로고" />

        <input
          type="text"
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSubmitSearch()
          }}
          placeholder={translate('askAiAboutKnowledgeGraph', 'ko')}
          className="flex-1 bg-transparent font-inter text-snap-white outline-none placeholder:text-snap-muted"
          style={{ fontSize: 14, lineHeight: '16.94px' }}
          aria-label="Ask AI about your knowledge graph"
        />

        <button
          onClick={onSubmitSearch}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
          style={{ background: value.trim() ? '#81ecff' : 'rgba(70,72,75,0.3)' }}
          aria-label="Send"
          disabled={!value.trim() || isSearching}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d="M7 12V2M3 6L7 2L11 6"
              stroke={value.trim() ? '#003840' : '#aaabaf'}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  )
}
