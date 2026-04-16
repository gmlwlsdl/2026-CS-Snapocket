'use client'

import { useState } from 'react'
import {t as translate} from '@/shared/lib/i18n'

interface AiInputBarProps {
  onSearch?: (value: string) => void
}

export function AiInputBar({ onSearch }: AiInputBarProps) {
  const [value, setValue] = useState('')

  const handleSearch = () => {
    if (value.trim()) {
      onSearch?.(value.trim())
    } else {
      onSearch?.('')
    }
  }

  return (
    <div className="absolute bottom-8 left-1/2 z-10 w-[672px] -translate-x-1/2">
      <div
        className="flex h-14 items-center gap-3 px-6"
        style={{
          background: 'rgba(23,26,29,0.7)',
          border: '1px solid rgba(70,72,75,0.15)',
          borderRadius: 9999,
          backdropFilter: 'blur(12px)',
        }}
      >
        {/* AI 아이콘 */}
        <img src="/ai.svg" alt="AI 로고" />

        {/* 인풋 */}
        <input
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            if (e.target.value === '') onSearch?.('')
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearch()
          }}
          placeholder={translate('askAiAboutKnowledgeGraph', 'ko')}
          className="flex-1 bg-transparent font-inter text-snap-white outline-none placeholder:text-snap-muted"
          style={{ fontSize: 14, lineHeight: '16.94px' }}
          aria-label="Ask AI about your knowledge graph"
        />

        <button
          onClick={handleSearch}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
          style={{ background: value ? '#81ecff' : 'rgba(70,72,75,0.3)' }}
          aria-label="Send"
          disabled={!value}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d="M7 12V2M3 6L7 2L11 6"
              stroke={value ? '#003840' : '#aaabaf'}
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
