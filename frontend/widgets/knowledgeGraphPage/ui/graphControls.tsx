'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import { Tooltip } from '@mantine/core'

import {ArrowsOutIcon, MagnifyingGlassPlusIcon, MagnifyingGlassMinusIcon}  from '@phosphor-icons/react'

interface GraphControlsProps {
  onZoomIn?: () => void
  onZoomOut?: () => void
  onFit?: () => void
  similarityThreshold?: number
  onSimilarityChange?: (value: number) => void
}

export function GraphControls({
  onZoomIn,
  onZoomOut,
  onFit,
  similarityThreshold = 0.64,
  onSimilarityChange,
}: GraphControlsProps) {
  const [draftThreshold, setDraftThreshold] = useState(similarityThreshold)

  useEffect(() => {
    setDraftThreshold(similarityThreshold)
  }, [similarityThreshold])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (draftThreshold !== similarityThreshold) {
        onSimilarityChange?.(draftThreshold)
      }
    }, 140)

    return () => window.clearTimeout(timer)
  }, [draftThreshold, onSimilarityChange, similarityThreshold])

  const panelBase: CSSProperties = {
    // background: 'var(--th-control-bg)',
    // border: '1px solid var(--th-control-border)',
    borderRadius: 8,
    backdropFilter: 'blur(8px)',
  }

  const iconBtn: CSSProperties = {
    ...panelBase,
    width: 40,
    height: 40,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
  }

  return (
    <div
      style={{
        position: 'absolute',
        right: 24,
        top: 80,
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <button
        style={iconBtn}
        className="hover:bg-[var(--th-surface-2)] active:scale-95 transition-all duration-150"
        aria-label="Zoom in"
        onClick={onZoomIn}
      >
        <MagnifyingGlassPlusIcon size={20} weight="fill" />
      </button>

      <button
        style={iconBtn}
        className="hover:bg-[var(--th-surface-2)] active:scale-95 transition-all duration-150"
        aria-label="Zoom out"
        onClick={onZoomOut}
      >
        <MagnifyingGlassMinusIcon size={20} weight="fill" />
      </button>

      <button
        style={{ ...iconBtn, color: 'var(--th-text-muted)' }}
        className="hover:bg-[var(--th-surface-2)] active:scale-95 transition-all duration-150"
        aria-label="Fit to screen"
        onClick={onFit}
      >
        <ArrowsOutIcon size={20} weight="fill" />
      </button>

      {/* 유사도 슬라이더 패널 */}
      <Tooltip
        label={`간선 유사도 임계값 ≥ ${draftThreshold.toFixed(2)}`}
        position="left"
        withArrow
        styles={{ tooltip: { fontSize: 11 } }}
      >
        <div
          style={{
            ...panelBase,
            width: 40,
            paddingTop: 10,
            paddingBottom: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
          }}
        >
          {/* 라벨 */}
          <span
            style={{
              fontSize: 7,
              fontWeight: 700,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: 'var(--th-text-faint)',
              writingMode: 'vertical-rl',
              userSelect: 'none',
              cursor: 'default',
              lineHeight: 1,
            }}
          >
            EDGE
          </span>

          {/*
            native <input type="range"> + writing-mode: vertical-lr
            브라우저가 직접 좌표 변환을 처리 → 커서 정확도 보장
            direction: rtl 로 위쪽이 max(1), 아래쪽이 min(0.3)
          */}
          <input
            type="range"
            min={0.3}
            max={1}
            step={0.01}
            value={draftThreshold}
            onChange={(e) => setDraftThreshold(parseFloat(e.target.value))}
            aria-label="간선 유사도 임계값"
            style={{
              writingMode: 'vertical-lr',
              direction: 'rtl',
              height: 88,
              width: 4,
              cursor: 'pointer',
              accentColor: '#97c2ec',
              background: 'transparent',
              appearance: 'auto',
            } as CSSProperties}
          />

          {/* 현재 값 */}
          <span
            style={{
              fontSize: 9,
              fontWeight: 600,
              color: '#97c2ec',
              letterSpacing: '0.04em',
              fontVariantNumeric: 'tabular-nums',
              userSelect: 'none',
            }}
          >
            {draftThreshold.toFixed(2)}
          </span>
        </div>
      </Tooltip>
    </div>
  )
}
