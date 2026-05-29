'use client'

import { useTheme } from '@/shared/lib/theme/themeContext'

import { MoonIcon, SunDimIcon } from '@phosphor-icons/react';

export function ThemeToggle({ className }: { className?: string }) {
  const { isDark, toggleTheme } = useTheme()

  //   const panelBase: React.CSSProperties = {
  //   // background: 'var(--th-control-bg)',
  //   // border: '1px solid var(--th-control-border)',
  //   borderRadius: 8,
  //   backdropFilter: 'blur(8px)',
  // }

  // const iconBtn: React.CSSProperties = {
  //   ...panelBase,
  //   width: 40,
  //   height: 40,
  //   display: 'flex',
  //   alignItems: 'center',
  //   justifyContent: 'center',
  //   cursor: 'pointer',
  // }

  return (
    <button
      onClick={toggleTheme}
      className={`flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${className ?? ''} hover:bg-[var(--th-surface-2)] active:scale-95 transition-all duration-150`}
      style={{
        color: 'var(--th-text-muted)',
      }}
      aria-label={isDark ? '라이트 모드로 전환' : '다크 모드로 전환'}
      title={isDark ? 'Light mode' : 'Dark mode'}
    >
      {isDark ? (
        <MoonIcon size={20} weight="fill" />
      ) : (
        <SunDimIcon size={20} weight="fill" />
      )}
    </button>
  )
}
