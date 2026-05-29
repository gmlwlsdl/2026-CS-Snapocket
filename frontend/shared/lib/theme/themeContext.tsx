'use client'

import { useMantineColorScheme, useComputedColorScheme } from '@mantine/core'

// MantineProvider 아래 어디서나 사용 가능한 통합 테마 훅
export function useTheme() {
  const { setColorScheme } = useMantineColorScheme()
  const colorScheme = useComputedColorScheme('light', { getInitialValueInEffect: true })
  const isDark = colorScheme === 'dark'

  const toggleTheme = () => setColorScheme(isDark ? 'light' : 'dark')

  return { theme: colorScheme as 'light' | 'dark', isDark, toggleTheme }
}

// 하위 호환을 위한 더미 Provider — MantineProvider로 대체됨
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
