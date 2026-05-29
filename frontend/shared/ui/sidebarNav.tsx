"use client";

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { getMe, logout } from '@/entities/auth'
import type { MeResponseData } from '@/entities/auth/api/auth.api.type'
import { useTheme } from '@/shared/lib/theme/themeContext'
import { useToast } from '@/shared/lib/toast/toastContext'

import { CalendarBlankIcon, GraphIcon, FolderSimplePlusIcon, SignOutIcon, UserCircleIcon } from '@phosphor-icons/react'


interface SidebarNavProps {
  onUpload?: () => void
}

export function SidebarNav({ onUpload }: SidebarNavProps) {
  const router = useRouter()
  const { isDark } = useTheme()
  const { toast } = useToast()
  const [isOpen, setIsOpen] = useState(false)
  const [hoveredItem, setHoveredItem] = useState<'graph' | 'calendar' | null>(null)
  const [user, setUser] = useState<MeResponseData | null>(null)
  const pathname = usePathname()

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch((err) => {
        console.warn('Failed to fetch user profile:', err)
        setUser(null)
      })
  }, [])

  const handleLogout = () => {
    toast.runWithCountdown({
      title: '로그아웃 예약',
      message: '이 알림을 닫으면 로그아웃이 취소됩니다.',
      actionLabel: '로그아웃',
      duration: 4000,
      color: 'red',
      onComplete: async () => {
        try {
          await logout()
          router.push('/login')
        } catch (err) {
          console.error('Failed to logout:', err)
          const { clearAccessToken } = await import('@/shared/api')
          clearAccessToken()
          router.push('/login')
        }
      },
    })
  }

  const isGraph = pathname === '/'
  const isCalendar = pathname === '/calendar'
  const isGraphHighlighted = isGraph || hoveredItem === 'graph'
  const isCalendarHighlighted = isCalendar || hoveredItem === 'calendar'

  const inactiveIconFill = isDark ? '#FFFFFF' : '#4c4546'

  return (
    <aside
      className="fixed left-0 top-16 z-30 flex flex-col justify-between overflow-hidden py-6 transition-[width] duration-300 ease-in-out"
      style={{
        width: isOpen ? 256 : 81,
        height: 'calc(100vh - 64px)',
        background: isDark ? '#0c0e11' : '#FFFFFF'
        // borderRight: '1px solid var(--th-border)',
      }}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      {/* 상단: 네비게이션 + CTA */}
      <div className="flex flex-col gap-6">
        {/* 네비게이션 탭 */}
        <nav className="flex flex-col">
          {/* Graph View */}
          <Link
            href="/"
            className="sidebar-nav-item relative flex items-center py-3 pl-[19px] transition-colors"
            style={{
              background: isGraph ? 'rgba(151,194,236,0.08)' : 'transparent',
              borderLeft: isGraph
                ? '2px solid #97c2ec'
                : '2px solid transparent',
            }}
            onMouseEnter={() => setHoveredItem('graph')}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <div className="flex h-6 w-[43px] shrink-0 items-center justify-center">
              <GraphIcon size={20} fill={isGraphHighlighted ? "#97c2ec" : inactiveIconFill} />
            </div>
            <span
              className="font-inter text-sm transition-all duration-300 overflow-hidden"
              style={{
                fontWeight: isGraph ? 700 : 400,
                color: isGraphHighlighted ? '#97c2ec' : 'var(--th-text-muted)',
                letterSpacing: '-0.4px',
                opacity: isOpen ? 1 : 0,
                maxWidth: isOpen ? 120 : 0,
                whiteSpace: 'nowrap',
              }}
            >
              Graph View
            </span>
          </Link>

          {/* Calendar */}
          <Link
            href="/calendar"
            className="sidebar-nav-item flex items-center py-3 pl-[21px] transition-colors"
            style={{
              background: isCalendar ? 'rgba(151,194,236,0.08)' : 'transparent',
              borderLeft: isCalendar
                ? '2px solid #97c2ec'
                : '2px solid transparent',
            }}
            onMouseEnter={() => setHoveredItem('calendar')}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <div className="flex h-5 w-[41px] shrink-0 items-center justify-center">
                <CalendarBlankIcon size={20} fill={isCalendarHighlighted ? "#97c2ec" : inactiveIconFill} />            
            </div>
            <span
              className="font-inter text-sm transition-all duration-300 overflow-hidden"
              style={{
                fontWeight: isCalendar ? 700 : 400,
                color: isCalendarHighlighted ? '#97c2ec' : 'var(--th-text-muted)',
                letterSpacing: '-0.4px',
                opacity: isOpen ? 1 : 0,
                maxWidth: isOpen ? 120 : 0,
                whiteSpace: 'nowrap',
              }}
            >
              Calendar
            </span>
          </Link>
        </nav>

        {/* CTA 버튼 */}
        <div className="px-[19px]">
          <button
            className="sidebar-cta flex items-center justify-center rounded-xl transition-all duration-300 cursor-pointer"
            style={{
              background: 'linear-gradient(135deg, #97c2ec 0%, #7daed8 100%)',
              height: 52,
              width: isOpen ? 208 : 50,
            }}
            onClick={onUpload}
            aria-label="Upload new file"
          >
            <div className="flex shrink-0 items-center justify-center">
              <FolderSimplePlusIcon size={20} weight="fill" />
            </div>
            <span
              className="font-inter font-bold text-sm tracking-[1.4px] transition-all duration-300 overflow-hidden"
              style={{
                color: '#0d2b45',
                opacity: isOpen ? 1 : 0,
                maxWidth: isOpen ? 120 : 0,
                whiteSpace: 'nowrap',
                marginLeft: isOpen ? 8 : 0,
              }}
            >
              New Node
            </span>
          </button>
        </div>
      </div>

      {/* 하단: 설정, 지원, 프로필 */}
      <div className="flex flex-col">
        {/* 사용자 프로필 */}
        <div
          className="sidebar-profile flex items-center py-4 pl-[19px]"
          // style={{ borderTop: '1px solid var(--th-separator)' }}
        >
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full"
            style={{
              // border: '1px solid var(--th-border)',
              // background: isDark ? '#1a2a2a' : '#d8f5ea',
            }}
          >
            <UserCircleIcon size={20} weight="fill" />
          </div>

          <div
            className="ml-3 flex flex-col transition-all duration-300 overflow-hidden"
            style={{
              opacity: isOpen ? 1 : 0,
              maxWidth: isOpen ? 140 : 0,
              whiteSpace: 'nowrap',
            }}
          >
            <span
              className="font-inter font-bold text-xs"
              style={{ color: 'var(--th-text)', letterSpacing: '-0.4px' }}
            >
              {user?.name ?? "김스냅"}
            </span>
            <span
              className="font-inter text-[10px]"
              style={{ color: 'var(--th-text-muted)', letterSpacing: '-0.4px' }}
            >
              {user?.email ?? "kimsnap@gmail.com"}
            </span>
          </div>

          {isOpen && (
            <button
              onClick={handleLogout}
              className="ml-auto mr-4 text-red-400 hover:text-red-500 transition-colors p-1 cursor-pointer shrink-0"
              title="로그아웃"
            >
              <SignOutIcon size={20} weight="fill" />
            </button>
          )}
        </div>
      </div>

      <style>{`
        .sidebar-nav-item:hover {
          background: rgba(151, 194, 236, 0.08) !important;
        }

        .sidebar-nav-item:focus-visible {
          outline: 2px solid rgba(151, 194, 236, 0.7);
          outline-offset: -2px;
        }

        .sidebar-cta:hover {
          box-shadow: 0 10px 22px rgba(151, 194, 236, 0.28);
          filter: brightness(1.04);
          transform: translateY(-1px);
        }

        .sidebar-cta:focus-visible {
          outline: 2px solid rgba(151, 194, 236, 0.75);
          outline-offset: 3px;
        }

        .sidebar-profile {
          transition: background-color 160ms ease;
        }

        .sidebar-profile:hover {
          background: rgba(151, 194, 236, 0.06);
        }
      `}</style>
    </aside>
  )
}
