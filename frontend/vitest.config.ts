import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    tsconfigPaths(),
    react(),
    {
      // SVG → 최소 React 컴포넌트 mock (next-svgr은 Turbopack 전용이라 Vitest에선 별도 처리)
      name: 'svg-mock',
      transform(_, id) {
        if (id.endsWith('.svg')) {
          return {
            code: `
              import React from 'react'
              const Svg = (props) => React.createElement('svg', props)
              Svg.displayName = 'SvgMock'
              export default Svg
            `,
          }
        }
      },
    },
  ],
  test: {
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        // fetch('/api/...') 상대 경로가 동작하려면 base URL 필수
        // MSW 핸들러도 http://localhost/api/... 로 매칭됨
        url: 'http://localhost',
      },
    },
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['**/__tests__/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules/**', '.next/**', 'coverage/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      reportsDirectory: './coverage',
      include: ['entities/**', 'features/**', 'widgets/**', 'shared/**'],
      exclude: [
        '**/__tests__/**',
        '**/*.test.{ts,tsx}',
        '**/index.ts',
        '**/types.ts',
        '**/mock/**',
      ],
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, '.'),
      'next/navigation': resolve(__dirname, '__mocks__/next/navigation.ts'),
      'next/dynamic': resolve(__dirname, '__mocks__/next/dynamic.tsx'),
      'next/link': resolve(__dirname, '__mocks__/next/link.tsx'),
    },
  },
})
