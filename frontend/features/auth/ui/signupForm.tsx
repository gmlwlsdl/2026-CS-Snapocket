'use client'

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { signup } from '@/entities/auth/api'
import { ApiError } from '@/shared/api'

export function SignupForm() {
  const router = useRouter()
  const [form, setForm] = useState({ email: '', password: '', name: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  function handleChange(field: 'email' | 'password' | 'name') {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setErrorMessage(null)
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setIsLoading(true)
    setErrorMessage(null)
    setSuccessMessage(null)

    if (!form.email || !form.password || !form.name) {
      setErrorMessage('모든 필수 항목을 입력해주세요.')
      setIsLoading(false)
      return
    }

    try {
      await signup({ email: form.email, password: form.password, name: form.name })
      setSuccessMessage('회원가입에 성공했습니다! 로그인 페이지로 이동합니다.')
      setTimeout(() => {
        router.push('/login')
      }, 1500)
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message)
      } else {
        setErrorMessage('회원가입에 실패했습니다. 다시 시도해주세요.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        {/* 이름 필드 */}
        <div className="flex flex-col gap-2">
          <label
            htmlFor="name"
            className="font-inter text-[10px] text-snap-muted tracking-[1.5px] uppercase"
          >
            Name
          </label>
          <input
            id="name"
            type="text"
            placeholder="John Doe"
            value={form.name}
            onChange={handleChange('name')}
            required
            className="w-full h-[51px] rounded-lg bg-snap-input px-4 font-inter text-base text-snap-white placeholder:text-snap-muted/30 outline-none focus:ring-1 focus:ring-snap-cyan/40 transition"
          />
        </div>

        {/* 이메일 필드 */}
        <div className="flex flex-col gap-2">
          <label
            htmlFor="email"
            className="font-inter text-[10px] text-snap-muted tracking-[1.5px] uppercase"
          >
            Email Address
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="name@company.com"
            value={form.email}
            onChange={handleChange('email')}
            required
            className="w-full h-[51px] rounded-lg bg-snap-input px-4 font-inter text-base text-snap-white placeholder:text-snap-muted/30 outline-none focus:ring-1 focus:ring-snap-cyan/40 transition"
          />
        </div>

        {/* 패스워드 필드 */}
        <div className="flex flex-col gap-2">
          <label
            htmlFor="password"
            className="font-inter text-[10px] text-snap-muted tracking-[1.5px] uppercase"
          >
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="••••••••"
              value={form.password}
              onChange={handleChange('password')}
              required
              className="w-full h-[51px] rounded-lg bg-snap-input px-4 pr-12 font-inter text-base text-snap-white placeholder:text-snap-muted/30 outline-none focus:ring-1 focus:ring-snap-cyan/40 transition"
            />
            <button
              type="button"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-snap-muted/50 hover:text-snap-muted transition-colors"
            >
              {showPassword ? (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {errorMessage !== null && (
          <p role="alert" className="font-inter text-[13px] text-red-400">
            {errorMessage}
          </p>
        )}

        {successMessage !== null && (
          <p role="alert" className="font-inter text-[13px] text-snap-cyan">
            {successMessage}
          </p>
        )}

        {/* 가입 버튼 */}
        <button
          type="submit"
          disabled={isLoading}
          className="relative w-full h-14 rounded-lg font-manrope font-bold text-base text-snap-btn-text overflow-hidden transition-opacity hover:opacity-90 mt-4 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
          style={{
            background: 'linear-gradient(135deg, #81ecff 0%, #00e3fd 100%)',
          }}
        >
          {isLoading ? 'Creating Account…' : 'Create Account'}
        </button>
      </form>
    </div>
  )
}
