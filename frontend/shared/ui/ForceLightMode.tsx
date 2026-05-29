'use client'

import type { ReactNode } from 'react'

export function ForceLightMode({ children }: { children: ReactNode }) {
  return (
    <div
      data-mantine-color-scheme="light"
      style={{
        '--th-bg': '#ffffff',
        '--th-panel': '#f5f2ec',
        '--th-sidebar': '#f9f7f3',
        '--th-surface': '#ede8df',
        '--th-surface-2': '#e4dfd5',
        '--th-text': '#1f1f1f',
        '--th-text-muted': '#4a4540',
        '--th-text-faint': '#7e7975',
        '--th-header-bg': 'rgba(255,255,255,0.88)',
        '--th-separator': 'rgba(0,0,0,0.06)',
        '--th-border': 'rgba(162,155,144,0.3)',
        '--th-chip-active-bg': '#97c2ec',
        '--th-chip-active-text': '#0d2b45',
        '--th-chip-inactive-bg': '#ede8df',
        '--th-chip-inactive-border': 'rgba(162,155,144,0.25)',
        '--th-chip-inactive-text': '#4a4540',
        '--mantine-color-body': '#ffffff',
        '--mantine-color-text': '#1f1f1f',
        '--mantine-color-default': '#ede8df',
        '--mantine-color-dimmed': '#4a4540',
      } as React.CSSProperties}
    >
      {children}
    </div>
  )
}
