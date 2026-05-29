'use client'

import { SignupForm } from "@/features/auth"
import { Anchor, Text } from "@mantine/core"
import { ForceLightMode } from "@/shared/ui"
import Link from "next/link"
import { useEffect } from "react"
import { clearAccessToken } from "@/shared/api"

export function SignupPage() {
  useEffect(() => {
    // 회원가입 화면 진입 시에도 만료된 세션 쿠키가 잔존하여
    // 미들웨어/프록시가 로그인 유저로 오인해 대시보드로 무한 리다이렉트하는 현상을 원천 방지합니다.
    clearAccessToken();
  }, []);

  return (
    <ForceLightMode>
    <div className="flex min-h-screen w-full font-inter justify-center" style={{ background: 'var(--th-bg)' }}>
      <section className="flex flex-col w-full lg:w-1/2" style={{ background: 'var(--th-bg)' }}>
        <div className="flex flex-1 flex-col justify-center px-8 sm:px-16 lg:px-[100px]">
          <div className="w-full max-w-[448px] mx-auto flex flex-col gap-8">
            {/* 헤더 */}
            <div className="flex flex-col gap-2">
              <h2
                className="font-manrope font-bold"
                style={{ fontSize: 30, letterSpacing: -0.75, lineHeight: "36px", color: 'var(--th-text)' }}
              >
                회원가입
              </h2>
            </div>

            <SignupForm />

            <Text ta="center" size="sm" c="dimmed">
              이미 계정이 있으신가요?{" "}
              <Link
                href="/login"
                style={{
                  color: 'var(--th-chip-active-bg, #97c2ec)',
                  fontWeight: 600,
                  textDecoration: 'underline',
                  fontSize: 'inherit',
                  fontFamily: 'inherit',
                }}
                className="hover:opacity-80 transition-opacity"
              >
                로그인
              </Link>
            </Text>
          </div>
        </div>

        <footer className="flex items-center justify-center px-8 sm:px-12 py-5">
          <Text size="xs" c="dimmed" style={{ letterSpacing: 1 }}>
            © 2026 Snapocket AI.
          </Text>
        </footer>
      </section>
    </div>
    </ForceLightMode>
  )
}
