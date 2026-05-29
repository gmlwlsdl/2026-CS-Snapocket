'use client'

import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { theme, cssVariablesResolver } from './theme'

export function MantineClientProvider({ children }: { children: React.ReactNode }) {
  return (
    <MantineProvider
      theme={theme}
      cssVariablesResolver={cssVariablesResolver}
      defaultColorScheme="light"
    >
      <Notifications position="bottom-right" zIndex={9999} />
      {children}
    </MantineProvider>
  )
}
