'use client'

import { useTheme } from '@/shared/lib/theme/themeContext'

interface GraphControlsProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFit?: () => void;
}

export function GraphControls({ onZoomIn, onZoomOut, onFit }: GraphControlsProps) {
  const { isDark } = useTheme()
  const imgFilter = isDark ? 'none' : 'brightness(0) opacity(0.5)'

  return (
    <div className="absolute right-6 top-20 z-10 flex flex-col gap-2">
      {/* 줌 인 */}
      <button
        className="flex h-10 w-10 items-center justify-center transition-colors"
        style={{
          background: 'var(--th-control-bg)',
          border: '1px solid var(--th-control-border)',
          borderRadius: 8,
          backdropFilter: 'blur(8px)',
        }}
        aria-label="Zoom in"
        onClick={onZoomIn}
      >
        <img src="/zoomIn.svg" alt="Zoom in 아이콘" style={{ filter: imgFilter }} />
      </button>

      {/* 줌 아웃 */}
      <button
        className="flex h-10 w-10 items-center justify-center transition-colors"
        style={{
          background: 'var(--th-control-bg)',
          border: '1px solid var(--th-control-border)',
          borderRadius: 8,
          backdropFilter: 'blur(8px)',
        }}
        aria-label="Zoom out"
        onClick={onZoomOut}
      >
        <img src="/zoomOut.svg" alt="Zoom out 아이콘" style={{ filter: imgFilter }} />
      </button>

      {/* 전체 화면 맞춤 */}
      <button
        className="flex h-10 w-10 items-center justify-center transition-colors"
        style={{
          background: 'var(--th-control-bg)',
          border: '1px solid var(--th-control-border)',
          borderRadius: 8,
          backdropFilter: 'blur(8px)',
          color: 'var(--th-text-muted)',
        }}
        aria-label="Fit to screen"
        onClick={onFit}
      >
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <path
            d="M3 8V3H8M14 3H19V8M19 14V19H14M8 19H3V14"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M8 11H14M11 8V14"
            stroke="currentColor"
            strokeWidth="1"
            strokeLinecap="round"
            opacity="0.5"
          />
        </svg>
      </button>
    </div>
  );
}
