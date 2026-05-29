'use client'

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { TextInput, PasswordInput, Button, Text } from '@mantine/core'
import { signup } from '@/entities/auth/api'
import { ApiError } from '@/shared/api'

export function SignupForm() {
  const router = useRouter()
  const [form, setForm] = useState({ email: '', password: '', name: '' })
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
      setTimeout(() => router.push('/login'), 1500)
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError ? err.message : '회원가입에 실패했습니다. 다시 시도해주세요.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  const labelStyles = { fontSize: 10, letterSpacing: '1.5px', textTransform: 'uppercase' as const }
  const inputStyles = { input: { height: 51 } }

  return (
    <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <TextInput
        id="name"
        label="이름"
        placeholder="이름을 입력해주세요"
        value={form.name}
        onChange={handleChange('name')}
        required
        styles={{ label: labelStyles, ...inputStyles }}
      />

      <TextInput
        id="email"
        label="이메일"
        type="email"
        autoComplete="email"
        placeholder="이메일을 입력해주세요"
        value={form.email}
        onChange={handleChange('email')}
        required
        styles={{ label: labelStyles, ...inputStyles }}
      />

      <PasswordInput
        id="password"
        label="비밀번호"
        autoComplete="new-password"
        placeholder="비밀번호를 입력해주세요"
        value={form.password}
        onChange={handleChange('password')}
        required
        styles={{ label: labelStyles, ...inputStyles }}
      />

      {errorMessage && (
        <Text role="alert" size="sm" c="red">
          {errorMessage}
        </Text>
      )}
      {successMessage && (
        <Text role="alert" size="sm" c="snap">
          {successMessage}
        </Text>
      )}

      <Button
        type="submit"
        loading={isLoading}
        fullWidth
        size="lg"
        mt="sm"
        radius="md"
        style={{
          background: 'linear-gradient(135deg, #97c2ec 0%, #7daed8 100%)',
          color: '#0d2b45',
          fontFamily: 'var(--font-manrope), Manrope, sans-serif',
          fontWeight: 700,
        }}
      >
        {isLoading ? '회원가입 중…' : '회원가입'}
      </Button>
    </form>
  )
}
