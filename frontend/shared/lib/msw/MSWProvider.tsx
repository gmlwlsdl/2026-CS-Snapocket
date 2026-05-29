'use client';

import { useEffect, useState, type ReactNode } from 'react';

const IS_MSW_ENABLED = process.env.NEXT_PUBLIC_MSW_ENABLED === 'true';

let initialized = false;

async function startMSW() {
  if (typeof window === 'undefined') return;
  const { worker } = await import('@/mocks/browser');
  await worker.start({
    onUnhandledRequest: 'bypass',
    serviceWorker: { url: '/mockServiceWorker.js' },
  });

  // 미들웨어의 쿠키 기반 인증 체크를 통과하기 위해 mock 토큰을 쿠키에 설정
  if (!document.cookie.includes('access_token')) {
    document.cookie = `access_token=mock-access-token-snapocket-dev-2026; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
  }
}

export function MSWProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(!IS_MSW_ENABLED || initialized);

  useEffect(() => {
    if (!IS_MSW_ENABLED || initialized) {
      setReady(true);
      return;
    }
    startMSW().then(() => {
      initialized = true;
      setReady(true);
    });
  }, []);

  if (!ready) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f9fafb',
          zIndex: 9999,
          fontFamily: 'sans-serif',
          color: '#6b7280',
          fontSize: '14px',
          gap: '10px',
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
        MSW Mock 환경 초기화 중...
      </div>
    );
  }

  return <>{children}</>;
}
