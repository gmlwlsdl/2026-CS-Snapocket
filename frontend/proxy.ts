import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// 보호할 라우트와 비인가 진입 허용 라우트 정의
const PROTECTED_ROUTES = ['/', '/calendar', '/analysis']
const AUTH_ROUTES = ['/login', '/signup']

export function proxy(request: NextRequest) {
  const token = request.cookies.get('access_token')?.value
  const { pathname } = request.nextUrl

  // 정적 자원(static), 이미지, favicon 등은 미들웨어 검사에서 제외
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/static') ||
    pathname.startsWith('/api') ||
    pathname.includes('.')
  ) {
    return NextResponse.next()
  }

  // 1. 비로그인 사용자가 보호된 라우트로 진입 시도 시 즉시 로그인으로 차단
  const isProtectedRoute = PROTECTED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith('/analysis/')
  )
  if (isProtectedRoute && !token) {
    const loginUrl = new URL('/login', request.url)
    return NextResponse.redirect(loginUrl)
  }

  // 2. 로그인된 사용자가 로그인/회원가입 페이지 재진입 시도 시 메인 대시보드로 리다이렉트
  const isAuthRoute = AUTH_ROUTES.some((route) => pathname === route)
  if (isAuthRoute && token) {
    const homeUrl = new URL('/', request.url)
    return NextResponse.redirect(homeUrl)
  }

  return NextResponse.next()
}
