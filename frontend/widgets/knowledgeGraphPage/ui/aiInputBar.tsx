'use client'

import { t as translate } from '@/shared/lib/i18n'
import { useTheme } from '@/shared/lib/theme/themeContext'

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
  const { isDark } = useTheme()

  const statusLabel = isSearching
    ? '검색 중'
    : aiAvailable
      ? modeUsed === 'semantic'
        ? 'AI 임베딩 검색'
        : '텍스트 검색 + AI 대기'
      : '텍스트 검색만 가능'

  const statusStyle = aiAvailable
    ? isDark
      ? {
          background: 'rgba(129,236,255,0.16)',
          color: '#b9f8ff',
          border: '1px solid rgba(129,236,255,0.28)',
        }
      : {
          background: 'rgba(166,242,207,0.3)',
          color: '#1b6b4f',
          border: '1px solid rgba(166,242,207,0.5)',
        }
    : isDark
      ? {
          background: 'rgba(170,171,175,0.16)',
          color: '#d2d5da',
          border: '1px solid rgba(170,171,175,0.2)',
        }
      : {
          background: 'rgba(76,69,70,0.08)',
          color: 'var(--th-text-muted)',
          border: '1px solid var(--th-border)',
        }

  return (
    <div className="absolute bottom-8 left-1/2 z-10 w-[672px] -translate-x-1/2">
      <div className="mb-2 flex justify-center">
        <span className="rounded-full px-3 py-1 text-xs" style={statusStyle}>
          {statusLabel}
        </span>
      </div>
      <div
        className="flex h-14 items-center gap-3 px-6"
        style={{
          background: 'var(--th-ai-bar-bg)',
          border: '1px solid var(--th-ai-bar-border)',
          borderRadius: 9999,
          backdropFilter: 'blur(12px)',
        }}
      >
        <img
          src="/ai.svg"
          alt="AI 로고"
          style={{ filter: isDark ? 'none' : 'brightness(0) opacity(0.5)' }}
        />

        <input
          type="text"
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSubmitSearch()
          }}
          placeholder={translate('askAiAboutKnowledgeGraph', 'ko')}
          className="flex-1 bg-transparent font-inter outline-none th-placeholder"
          style={{ fontSize: 14, lineHeight: '16.94px', color: 'var(--th-text)' }}
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
              stroke={value.trim() ? '#003840' : 'var(--th-text-faint)'}
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
