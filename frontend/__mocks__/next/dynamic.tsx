import React from 'react'

type DynamicOptions = {
  ssr?: boolean
  loading?: () => React.ReactNode
}

// next/dynamic mock — ssr:false 컴포넌트는 Canvas/WebGL 없이 placeholder를 반환
function dynamic(
  _importFn: () => Promise<unknown>,
  options: DynamicOptions = {},
): React.ComponentType {
  if (options.ssr === false) {
    const Placeholder = () =>
      React.createElement('div', { 'data-testid': 'dynamic-ssr-false' })
    Placeholder.displayName = 'DynamicSSRFalsePlaceholder'
    return Placeholder
  }

  // ssr:true(기본값) — Suspense + lazy로 동기 로드
  const LazyComponent = React.lazy(async () => {
    const mod = await _importFn() as Record<string, React.ComponentType>
    const Component = ('default' in mod ? mod.default : Object.values(mod)[0]) as React.ComponentType
    return { default: Component }
  })

  const Wrapper = (props: Record<string, unknown>) =>
    React.createElement(
      React.Suspense,
      { fallback: null },
      React.createElement(LazyComponent, props),
    )
  Wrapper.displayName = 'DynamicWrapper'
  return Wrapper
}

export default dynamic
