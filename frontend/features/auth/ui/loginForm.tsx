'use client'

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { TextInput, PasswordInput, Button, Text, Anchor } from '@mantine/core'
import type { LoginFormState } from '@/features/auth/loginForm.type'
import { login } from '@/entities/auth/api'
import { ApiError } from '@/shared/api'

export function LoginForm() {
  const router = useRouter()
  const [form, setForm] = useState<LoginFormState>({ email: '', password: '' })
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  function handleChange(field: keyof LoginFormState) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setErrorMessage(null)
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setIsLoading(true)
    setErrorMessage(null)

    if (process.env.NODE_ENV === 'development') {
      const { saveAccessToken } = await import('@/shared/api')
      saveAccessToken('dev-mock-token')
      router.push('/')
      return
    }

    try {
      await login({ email: form.email, password: form.password })
      router.push('/')
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError ? err.message : '로그인에 실패했습니다. 다시 시도해주세요.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <TextInput
        id="email"
        label="Email Address"
        type="email"
        autoComplete="email"
        placeholder="name@company.com"
        value={form.email}
        onChange={handleChange('email')}
        required
        styles={{
          label: { fontSize: 11, letterSpacing: '1.5px', textTransform: 'uppercase' },
          input: { height: 51 },
        }}
      />

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Text size="xs" style={{ letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--mantine-color-dimmed)' }}>
            Password
          </Text>
          {/* TODO: [API] 비밀번호 재설정 엔드포인트 확정 후 연결 */}
          <Anchor size="xs" c="snap" fw={600} style={{ letterSpacing: '0.5px' }}>
            Forgot?
          </Anchor>
        </div>
        <PasswordInput
          id="password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={form.password}
          onChange={handleChange('password')}
          required
          styles={{ input: { height: 51 } }}
        />
      </div>

      {errorMessage && (
        <Text role="alert" size="sm" c="red">
          {errorMessage}
        </Text>
      )}

      <Button
        type="submit"
        loading={isLoading}
        fullWidth
        size="lg"
        mt="xs"
        radius="md"
        style={{
          background: 'linear-gradient(135deg, #97c2ec 0%, #7daed8 100%)',
          color: '#0d2b45',
          fontFamily: 'var(--font-manrope), Manrope, sans-serif',
          fontWeight: 700,
        }}
      >
        {isLoading ? 'Signing in…' : 'Sign In'}
      </Button>
    </form>
  )
}
