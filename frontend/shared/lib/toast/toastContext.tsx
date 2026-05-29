'use client'

import React, { createContext, useContext, useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { Progress } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { ApiError } from '@/shared/api'

export interface ToastItem {
  id: string
  fileName?: string
  message?: string
  status: 'processing' | 'complete' | 'error'
  analysisId?: string
}

interface CountdownActionOptions {
  title: string
  message?: string
  actionLabel?: string
  duration?: number
  color?: string
  onComplete: () => void | Promise<void>
}

interface ToastContextType {
  toastItems: ToastItem[]
  showToast: (item: Omit<ToastItem, 'id'> & { id?: string }) => string
  dismissToast: (id: string) => void
  updateToast: (id: string, updates: Partial<ToastItem>) => void
  toast: {
    success: (message: string, duration?: number) => void
    error: (errorOrMessage: unknown, defaultMessage?: string, duration?: number) => void
    info: (message: string, duration?: number) => void
    runWithCountdown: (options: CountdownActionOptions) => string
  }
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

function getErrorMessage(error: unknown, defaultMsg: string): string {
  if (error instanceof ApiError && error.message) return error.message
  if (error instanceof Error && error.message) return error.message
  return defaultMsg
}

function UploadMessage({ item }: { item: ToastItem }) {
  const isComplete = item.status === 'complete'
  const isError = item.status === 'error'

  const handleClick = () => {
    if (isComplete && item.analysisId) {
      window.location.href = `/analysis/${item.analysisId}?mode=result`
    }
  }

  return (
    <div
      onClick={isComplete ? handleClick : undefined}
      style={{ cursor: isComplete ? 'pointer' : 'default' }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.4 }}>
        {isComplete ? '분석 완료' : isError ? '분석 실패' : '분석 중…'}
      </div>
      {item.fileName && (
        <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{item.fileName}</div>
      )}
      {isComplete && item.analysisId && (
        <div style={{ fontSize: 10, opacity: 0.6, marginTop: 4, letterSpacing: '0.5px' }}>
          클릭하여 결과 보기
        </div>
      )}
    </div>
  )
}

function CountdownActionMessage({
  title,
  message,
  actionLabel = '실행',
  duration,
  notificationId,
  color = 'snap',
  onComplete,
}: {
  title: string
  message?: string
  actionLabel?: string
  duration: number
  notificationId: string
  color?: string
  onComplete: () => void | Promise<void>
}) {
  const [remainingMs, setRemainingMs] = useState(duration)
  const completedRef = useRef(false)

  useEffect(() => {
    const startedAt = Date.now()
    const interval = window.setInterval(() => {
      setRemainingMs(Math.max(0, duration - (Date.now() - startedAt)))
    }, 50)

    const timeout = window.setTimeout(async () => {
      if (completedRef.current) return
      completedRef.current = true
      await onComplete()
      notifications.hide(notificationId)
    }, duration)

    return () => {
      window.clearInterval(interval)
      window.clearTimeout(timeout)
    }
  }, [duration, notificationId, onComplete])

  const progressValue = Math.max(0, Math.min(100, (remainingMs / duration) * 100))
  const seconds = Math.ceil(remainingMs / 1000)

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.4 }}>{title}</div>
      {message && (
        <div style={{ marginTop: 4, fontSize: 12, lineHeight: 1.45, opacity: 0.72 }}>
          {message}
        </div>
      )}
      <div style={{ marginTop: 10, fontSize: 11, fontWeight: 600, opacity: 0.72 }}>
        닫지 않으면 {seconds}초 뒤 {actionLabel}됩니다.
      </div>
      <Progress
        value={progressValue}
        color={color}
        size="xs"
        radius="xl"
        mt={8}
        styles={{
          root: { background: 'rgba(170, 171, 175, 0.18)' },
          section: { transitionDuration: '80ms' },
        }}
      />
    </div>
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  // 업로드 추적용 상태 (knowledgeGraphPage 폴링에서 사용됨)
  const [toastItems, setToastItems] = useState<ToastItem[]>([])

  const dismissToast = useCallback((id: string) => {
    setToastItems((prev) => prev.filter((item) => item.id !== id))
    notifications.hide(id)
  }, [])

  const showToast = useCallback(
    (item: Omit<ToastItem, 'id'> & { id?: string }) => {
      const id = item.id || Math.random().toString(36).substring(2, 9)
      const newItem: ToastItem = { ...item, id }

      setToastItems((prev) => [newItem, ...prev])

      notifications.show({
        id,
        message: <UploadMessage item={newItem} />,
        loading: newItem.status === 'processing',
        color: newItem.status === 'error' ? 'red' : 'snap',
        autoClose: newItem.status === 'processing' ? false : 5000,
        withCloseButton: true,
        onClose: () => setToastItems((prev) => prev.filter((i) => i.id !== id)),
      })

      return id
    },
    [],
  )

  const updateToast = useCallback(
    (id: string, updates: Partial<ToastItem>) => {
      setToastItems((prev) =>
        prev.map((item) => {
          if (item.id !== id) return item
          const updated = { ...item, ...updates }

          notifications.update({
            id,
            message: <UploadMessage item={updated} />,
            loading: updated.status === 'processing',
            color: updated.status === 'error' ? 'red' : 'snap',
            autoClose: updated.status === 'processing' ? false : 5000,
            withCloseButton: true,
          })

          return updated
        }),
      )
    },
    [],
  )

  const toast = useMemo(
    () => ({
      success: (message: string, duration = 3000) => {
        notifications.show({
          message,
          color: 'snap',
          autoClose: duration,
          withCloseButton: true,
        })
      },
      error: (errorOrMessage: unknown, defaultMessage = '요청에 실패했습니다.', duration = 4000) => {
        const message =
          typeof errorOrMessage === 'string'
            ? errorOrMessage
            : getErrorMessage(errorOrMessage, defaultMessage)
        notifications.show({
          message,
          color: 'red',
          autoClose: duration,
          withCloseButton: true,
        })
      },
      info: (message: string, duration = 3000) => {
        notifications.show({
          message,
          color: 'gray',
          autoClose: duration,
          withCloseButton: true,
        })
      },
      runWithCountdown: ({
        title,
        message,
        actionLabel,
        duration = 4500,
        color = 'snap',
        onComplete,
      }: CountdownActionOptions) => {
        const id = Math.random().toString(36).substring(2, 9)
        notifications.show({
          id,
          message: (
            <CountdownActionMessage
              title={title}
              message={message}
              actionLabel={actionLabel}
              duration={duration}
              notificationId={id}
              color={color}
              onComplete={onComplete}
            />
          ),
          color,
          autoClose: false,
          withCloseButton: true,
        })

        return id
      },
    }),
    [],
  )

  return (
    <ToastContext.Provider value={{ toastItems, showToast, dismissToast, updateToast, toast }}>
      {children}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within a ToastProvider')
  return context
}
