'use client'

import { t as translate } from '@/shared/lib/i18n'
import { useTheme } from '@/shared/lib/theme/themeContext'
import { TextInput } from '@mantine/core'

import {HeadCircuitIcon, PaperPlaneTiltIcon} from '@phosphor-icons/react'

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
  const canSubmit = Boolean(value.trim()) && !isSearching

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
          background: 'rgba(151,194,236,0.18)',
          color: '#beddf4',
          // border: '1px solid rgba(151,194,236,0.3)',
        }
      : {
          background: 'rgba(151,194,236,0.2)',
          color: '#1b4b7a',
          // border: '1px solid rgba(151,194,236,0.4)',
        }
    : isDark
      ? {
          background: 'rgba(170,171,175,0.16)',
          color: '#d2d5da',
          // border: '1px solid rgba(170,171,175,0.2)',
        }
      : {
          background: 'rgba(76,69,70,0.08)',
          color: 'var(--th-text-muted)',
          // border: '1px solid var(--th-border)',
        }

  return (
    <div className="absolute bottom-8 left-1/2 z-10 w-[672px] -translate-x-1/2">
      <div className="mb-2 flex justify-center">
        <span className="rounded-full px-3 py-1 text-xs" style={statusStyle}>
          {statusLabel}
        </span>
      </div>
      <div
        className="ai-input-shell flex h-14 items-center gap-3 pr-6 pl-3"
        style={{
          // background: 'var(--th-ai-bar-bg)',
          // border: '1px solid var(--th-ai-bar-border)',
          borderRadius: 9999,
          backdropFilter: 'blur(12px)',
        }}
      >

        <TextInput
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && canSubmit) onSubmitSearch() }}
          placeholder={translate('askAiAboutKnowledgeGraph', 'ko')}
          aria-label="Ask AI about your knowledge graph"
          variant="unstyled"
          style={{ flex: 1 }}
          styles={{
            input: {
              fontSize: 14,
              lineHeight: '16.94px',
              color: 'var(--th-text)',
              // background: 'transparent',
              fontFamily: 'var(--font-inter), Inter, sans-serif',
            },
          }}
          leftSection={<HeadCircuitIcon size={20} weight="fill" />}
        />

        <button
          onClick={onSubmitSearch}
          className="ai-input-send flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
          style={{
            // background: canSubmit ? '#97c2ec' : 'rgba(70,72,75,0.3)',
          }}
          aria-label="Send"
          disabled={!canSubmit}
        >
          <PaperPlaneTiltIcon size={20} weight="fill" color={canSubmit ? isDark? '#97c2ec' : '#003840' : 'rgba(170,171,175,0.75)'}/>
        </button>
      </div>

      <style>{`
        .ai-input-shell {
          transition:
            background-color 160ms ease,
            border-color 160ms ease,
            box-shadow 160ms ease;
        }

        .ai-input-shell:hover,
        .ai-input-shell:focus-within {
          border-color: rgba(151, 194, 236, 0.65);
          box-shadow: 0 10px 30px rgba(151, 194, 236, 0.16);
          background-color:rgba(151, 194, 236, 0.2);
        }

        .ai-input-send {
          transition:
            background-color 160ms ease,
            box-shadow 160ms ease,
            transform 160ms ease,
            opacity 160ms ease;
        }

        .ai-input-send:not(:disabled):hover {
          // background: #acd0f0 !important;
          // box-shadow: 0 8px 18px rgba(151, 194, 236, 0.34);
          transform: translateY(-1px);
          cursor: pointer;
        }

        .ai-input-send:not(:disabled):focus-visible {
          outline: 2px solid rgba(151, 194, 236, 0.75);
          outline-offset: 3px;
        }

        .ai-input-send:disabled {
          cursor: not-allowed;
          opacity: 0.65;
        }
      `}</style>
    </div>
  )
}
