'use client'

import { t as translate } from '@/shared/lib/i18n'

export interface ToastItem {
  id: string
  fileName: string
  status: 'processing' | 'complete' | 'error'
  analysisId: string
}

interface ToastStatusProps {
  items: ToastItem[]
  onItemClick: (item: ToastItem) => void
  onCancel: (item: ToastItem) => void
}

export function ToastStatus({
  items,
  onItemClick,
  onCancel,
}: ToastStatusProps) {
  const visible = items.filter(
    (i) =>
      i.status === 'processing' ||
      i.status === 'complete' ||
      i.status === 'error',
  )
  if (visible.length === 0) return null

  return (
    <div className="absolute bottom-8 right-6 z-10 flex flex-col gap-2 w-[280px]">
      {visible.map((item) => (
        <ToastCard
          key={item.id}
          item={item}
          onClick={() => onItemClick(item)}
          onCancel={() => onCancel(item)}
        />
      ))}
    </div>
  )
}

function ToastCard({
  item,
  onClick,
  onCancel,
}: {
  item: ToastItem
  onClick: () => void
  onCancel: () => void
}) {
  const isComplete = item.status === 'complete'
  const isError = item.status === 'error'
  const isProcessing = item.status === 'processing'

  const borderColor = isComplete
    ? 'rgba(129,236,255,0.25)'
    : isError
      ? 'rgba(239,68,68,0.35)'
      : 'rgba(70,72,75,0.25)'

  return (
    <div
      onClick={isComplete ? onClick : undefined}
      className="flex flex-col gap-2 px-4 py-3 transition-all"
      style={{
        background: 'rgba(23,26,29,0.95)',
        border: `1px solid ${borderColor}`,
        borderRadius: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        backdropFilter: 'blur(12px)',
        cursor: isComplete ? 'pointer' : 'default',
      }}
      role={isComplete ? 'button' : 'status'}
      aria-live="polite"
    >
      {/* Row 1: indicator + label + action icon */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isComplete ? (
            <div
              className="h-2 w-2 rounded-full"
              style={{ background: '#81ecff' }}
            />
          ) : isError ? (
            <div
              className="h-2 w-2 rounded-full"
              style={{ background: '#ef4444' }}
            />
          ) : (
            <div
              className="h-2 w-2 rounded-full"
              style={{
                background: '#f59e0b',
                animation: 'toast-pulse 1.4s ease-in-out infinite',
              }}
            />
          )}
          <span
            className="font-inter"
            style={{ fontSize: 12, fontWeight: 600, color: '#f9f9fd' }}
          >
            {isComplete
              ? translate('analysisComplete', 'ko')
              : isError
                ? translate('analysisFailed', 'ko')
                : translate('analyzing', 'ko')}
          </span>
        </div>

        {isComplete ? (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M2 6L5 9L10 3"
              stroke="#81ecff"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : isProcessing ? (
          <div className="flex items-center gap-2">
            <div
              className="h-3 w-3 rounded-full border"
              style={{
                borderColor: 'rgba(245,158,11,0.2)',
                borderTopColor: '#f59e0b',
                animation: 'toast-spin 0.9s linear infinite',
              }}
            />
            <button
              onClick={(e) => {
                e.stopPropagation()
                onCancel()
              }}
              className="flex items-center justify-center"
              style={{ color: 'rgba(170,171,175,0.6)', lineHeight: 1 }}
              aria-label="취소"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path
                  d="M1 1L9 9M9 1L1 9"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
        ) : (
          /* error dismiss */
          <button
            onClick={(e) => {
              e.stopPropagation()
              onCancel()
            }}
            className="flex items-center justify-center  cursor-pointer"
            style={{ color: 'rgba(239,68,68,0.7)', lineHeight: 1 }}
            aria-label="닫기"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path
                d="M1 1L9 9M9 1L1 9"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Row 2: file name */}
      <span
        className="font-inter truncate"
        style={{ fontSize: 11, color: '#aaabaf' }}
        title={item.fileName}
      >
        {item.fileName}
      </span>

      {/* Click hint for complete */}
      {isComplete && (
        <div className="flex flex-col gap-1.5 mt-0.5">
          <span
            className="font-inter"
            style={{
              fontSize: 10,
              color: 'rgba(129,236,255,0.5)',
              letterSpacing: '0.8px',
            }}
          >
            {translate('clickToView', 'ko')}
          </span>
        </div>
      )}

      {/* Error hint */}
      {isError && (
        <span
          className="font-inter"
          style={{
            fontSize: 10,
            color: 'rgba(239,68,68,0.5)',
            letterSpacing: '0.8px',
          }}
        >
          분석 중 오류가 발생했어요.
        </span>
      )}

      <style>{`
        @keyframes toast-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @keyframes toast-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes toast-progress {
          0%   { transform: translateX(-40%); }
          100% { transform: translateX(80%); }
        }
      `}</style>
    </div>
  )
}
