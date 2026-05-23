'use client'

import React, { createContext, useContext, useState, useCallback, useMemo } from 'react'
import { ToastStatus, type ToastItem } from '@/shared/ui/toastStatus'
import { ApiError } from '@/shared/api'

interface ToastContextType {
  toastItems: ToastItem[]
  showToast: (item: Omit<ToastItem, 'id'> & { id?: string }) => string
  dismissToast: (id: string) => void
  updateToast: (id: string, updates: Partial<ToastItem>) => void
  toast: {
    success: (message: string, duration?: number) => string
    error: (errorOrMessage: unknown, defaultMessage?: string, duration?: number) => string
    info: (message: string, duration?: number) => string
  }
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

function getErrorMessage(error: unknown, defaultMsg: string): string {
  if (error instanceof ApiError && error.message) {
    return error.message
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return defaultMsg
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toastItems, setToastItems] = useState<ToastItem[]>([])

  const dismissToast = useCallback((id: string) => {
    setToastItems((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const showToast = useCallback(
    (item: Omit<ToastItem, 'id'> & { id?: string }) => {
      const id = item.id || Math.random().toString(36).substring(2, 9)
      const newItem: ToastItem = { ...item, id }

      setToastItems((prev) => [newItem, ...prev])

      // 일반 메시지 토스트이고, 진행 중이 아니면 자동 닫기 처리
      if (item.message && item.status !== 'processing') {
        const duration = item.duration ?? 3000
        setTimeout(() => {
          dismissToast(id)
        }, duration)
      }

      return id
    },
    [dismissToast],
  )

  const updateToast = useCallback(
    (id: string, updates: Partial<ToastItem>) => {
      setToastItems((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            const updated = { ...item, ...updates }
            // 상태가 완료나 에러로 바뀌었고 일반 메시지가 있으면 자동 닫기 예약
            if (updated.message && updated.status !== 'processing') {
              const duration = updated.duration ?? 3000
              setTimeout(() => {
                dismissToast(id)
              }, duration)
            }
            return updated
          }
          return item
        }),
      )
    },
    [dismissToast],
  )

  const toast = useMemo(
    () => ({
      success: (message: string, duration = 3000) =>
        showToast({
          message,
          status: 'complete',
          type: 'success',
          duration,
        }),
      error: (errorOrMessage: unknown, defaultMessage = '요청에 실패했습니다.', duration = 3000) => {
        const message =
          typeof errorOrMessage === 'string'
            ? errorOrMessage
            : getErrorMessage(errorOrMessage, defaultMessage)

        return showToast({
          message,
          status: 'error',
          type: 'error',
          duration,
        })
      },
      info: (message: string, duration = 3000) =>
        showToast({
          message,
          status: 'processing',
          type: 'info',
          duration,
        }),
    }),
    [showToast],
  )

  const handleToastClick = useCallback((item: ToastItem) => {
    if (item.status === 'complete' && item.analysisId) {
      // client-side navigation
      window.location.href = `/analysis/${item.analysisId}?mode=result`
    }
  }, [])

  return (
    <ToastContext.Provider
      value={{ toastItems, showToast, dismissToast, updateToast, toast }}
    >
      {children}
      <ToastStatus
        items={toastItems}
        onItemClick={handleToastClick}
        onCancel={(item) => dismissToast(item.id)}
      />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
