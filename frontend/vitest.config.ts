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
        '**/*.type.ts',       // 타입 정의 파일 — 로직 없음
        '**/*.constant.ts',   // 상수 파일 — 로직 없음
        '**/mock/**',
        // canvas·폴링·동적 import에 의존하는 widget 페이지 — jsdom에서 단위 테스트 불가
        'widgets/*/ui/*.tsx',
      ],
      thresholds: {
        // 임계값 미달 시 npm run test:coverage가 non-zero로 종료 → CI 실패
        // 신규 파일 추가 시 테스트 없이 머지되면 수치가 내려가 여기서 잡힘
        lines: 70,
        functions: 75,
        branches: 85,
      },
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
