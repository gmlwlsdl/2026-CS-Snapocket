'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { SidebarNav, ThemeToggle } from '@/shared/ui'
import { UploadModal } from '@/features/upload'
import { t as translate } from '@/shared/lib/i18n'
import {
  fetchCalendarMonth,
  fetchCalendarDay,
  type CalendarDates,
  type CalendarDayItem,
} from '@/entities/calendar'

const CATEGORY_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'lecture', label: 'Lecture' },
  { id: 'assignment', label: 'Assignment' },
  { id: 'notice', label: 'Notice' },
  { id: 'receipt', label: 'Receipt' },
  { id: 'memo', label: 'Memo' },
] as const

const WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일']

const MONTH_NAMES = [
  '1월', '2월', '3월', '4월', '5월', '6월',
  '7월', '8월', '9월', '10월', '11월', '12월',
]

const CATEGORY_COLOR: Record<string, string> = {
  lecture: '#ac89ff',
  assignment: '#81ecff',
  notice: '#fab0ff',
  receipt: '#ffd27f',
  memo: '#7ff0bb',
}

function getCategoryColor(category: string): string {
  return CATEGORY_COLOR[category] ?? '#aaabaf'
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

/** 해당 월 1일의 요일 (월요일 기준 0~6) */
function firstWeekdayOfMonth(year: number, month: number) {
  const day = new Date(year, month, 1).getDay() // 0=Sun
  return (day + 6) % 7 // 월=0 … 일=6
}

function buildGrid(year: number, month: number) {
  const totalDays = daysInMonth(year, month)
  const firstDay = firstWeekdayOfMonth(year, month)
  const prevMonthDays = daysInMonth(year, month - 1)

  const cells: { date: Date; current: boolean }[] = []

  // 이전 달 채우기
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({
      date: new Date(year, month - 1, prevMonthDays - i),
      current: false,
    })
  }

  // 이번 달
  for (let d = 1; d <= totalDays; d++) {
    cells.push({ date: new Date(year, month, d), current: true })
  }

  // 다음 달 (마지막 행 채우기)
  const tail = cells.length % 7
  if (tail !== 0) {
    for (let d = 1; d <= 7 - tail; d++) {
      cells.push({ date: new Date(year, month + 1, d), current: false })
    }
  }

  // 최소 5주 보장
  while (cells.length < 35) {
    const last = cells[cells.length - 1]
    const next = new Date(last.date)
    next.setDate(next.getDate() + 1)
    cells.push({ date: next, current: false })
  }

  return cells
}

function toKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatDateLabel(dateStr: string) {
  const [year, month, day] = dateStr.split('-')
  return `${year}년 ${Number(month)}월 ${Number(day)}일`
}

export function CalendarPage() {
  const router = useRouter()
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<'all' | 'lecture' | 'assignment' | 'notice' | 'receipt' | 'memo'>('all')
  const [calendarDates, setCalendarDates] = useState<CalendarDates>({})
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [dayItems, setDayItems] = useState<CalendarDayItem[]>([])
  const [dayPanelOpen, setDayPanelOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [uploadToast, setUploadToast] = useState<{
    visible: boolean
    fileName: string
  }>({ visible: false, fileName: '' })
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetchCalendarMonth({
      year,
      month: month + 1,
      category: activeFilter === 'all' ? undefined : activeFilter
    })
      .then(setCalendarDates)
      .catch((err) => console.error('Failed to load calendar:', err))
  }, [year, month, activeFilter])

  const cells = buildGrid(year, month)
  const rows: (typeof cells)[] = []
  for (let i = 0; i < cells.length; i += 7) {
    rows.push(cells.slice(i, i + 7))
  }

  const prevMonth = () => {
    if (month === 0) {
      setMonth(11)
      setYear((y) => y - 1)
    } else {
      setMonth((m) => m - 1)
    }
  }

  const nextMonth = () => {
    if (month === 11) {
      setMonth(0)
      setYear((y) => y + 1)
    } else {
      setMonth((m) => m + 1)
    }
  }

  const isToday = (d: Date) =>
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear()

  const getEvents = (d: Date) => {
    const items = calendarDates[toKey(d)] ?? []
    return items.map((item) => ({
      id: item.id,
      label: item.title,
      color: getCategoryColor(item.category),
    }))
  }

  const matchesSearch = (d: Date) => {
    if (!search.trim()) return true
    return getEvents(d).some((e) =>
      e.label.toLowerCase().includes(search.toLowerCase()),
    )
  }

  const handleDayClick = useCallback(async (date: Date) => {
    const dateStr = toKey(date)
    setSelectedDate(dateStr)
    setDayItems([])
    setDayPanelOpen(true)
    try {
      const items = await fetchCalendarDay({
        date: dateStr,
        category: activeFilter === 'all' ? undefined : activeFilter
      })
      setDayItems(items)
    } catch (err) {
      console.error('Failed to load day items:', err)
    }
  }, [activeFilter])

  const handleDayPanelClose = useCallback(() => {
    setDayPanelOpen(false)
    setSelectedDate(null)
    setDayItems([])
  }, [])

  const handleUpload = useCallback(async (file: File) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    setUploadToast({ visible: true, fileName: file.name })
 
    try {
      const { uploadDocument } = await import('@/entities/document')
      const uploadRes = await uploadDocument(file)
      
      setUploadToast({ visible: false, fileName: '' })
      router.push(`/analysis/${uploadRes.document_id}`)
    } catch (error) {
      console.error('Upload failed:', error)
      alert('파일 업로드에 실패했습니다. 다시 시도해 주세요.')
      setUploadToast({ visible: false, fileName: '' })
    }
  }, [router])

  return (
    <div
      className="flex h-screen w-full overflow-hidden"
      style={{ background: 'var(--th-bg)' }}
    >
      <SidebarNav onUpload={() => setModalOpen(true)} />

      <main
        className="flex flex-1 flex-col overflow-hidden"
        style={{ marginLeft: 81 }}
      >
        {/* ── 헤더 ─────────────────────────────────── */}
        <header
          className="flex shrink-0 items-center justify-between px-8"
          style={{
            height: 64,
            background: 'var(--th-header-bg)',
            borderBottom: '1px solid var(--th-separator)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <div className="flex items-center gap-6">
            <span
              className="font-manrope font-semibold text-sm"
              style={{ color: 'var(--th-text-faint)', letterSpacing: '1.4px' }}
            >
              SCHEDULE
            </span>

            <div className="flex items-center gap-2">
              <span
                className="font-manrope font-bold text-sm"
                style={{ color: '#81ecff', letterSpacing: '1.4px' }}
              >
                {MONTH_NAMES[month].toUpperCase()} {year}
              </span>

              <button
                onClick={prevMonth}
                className="flex h-5 w-4 items-center justify-center rounded transition-opacity hover:opacity-70"
                aria-label="이전 달"
                style={{ color: 'var(--th-text-faint)' }}
              >
                <svg width="7" height="12" viewBox="0 0 7 12" fill="none">
                  <path
                    d="M6 1L1 6L6 11"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

              <button
                onClick={nextMonth}
                className="flex h-5 w-4 items-center justify-center rounded transition-opacity hover:opacity-70"
                aria-label="다음 달"
                style={{ color: 'var(--th-text-faint)' }}
              >
                <svg width="7" height="12" viewBox="0 0 7 12" fill="none">
                  <path
                    d="M1 1L6 6L1 11"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          </div>

          {/* 카테고리 필터 칩 */}
          <nav className="flex items-center gap-2" aria-label="Category filters">
            {CATEGORY_FILTERS.map(({ id, label }) => {
              const isActive = activeFilter === id;
              return (
                <button
                  key={id}
                  onClick={() => setActiveFilter(id)}
                  className="flex items-center px-4 h-[28px] rounded-full font-manrope transition-colors cursor-pointer"
                  style={
                    isActive
                      ? {
                          background: 'var(--th-chip-active-bg)',
                          color: 'var(--th-chip-active-text)',
                          fontSize: 12,
                          fontWeight: 500,
                          letterSpacing: -0.4,
                        }
                      : {
                          background: 'var(--th-chip-inactive-bg)',
                          border: '1px solid var(--th-chip-inactive-border)',
                          color: 'var(--th-chip-inactive-text)',
                          fontSize: 12,
                          fontWeight: 500,
                          letterSpacing: -0.4,
                        }
                  }
                >
                  {label}
                </button>
              );
            })}
          </nav>

          {/* 검색 + 테마 토글 */}
          <div className="flex items-center gap-3">
            <div
              className="flex items-center gap-2 rounded-full px-4"
              style={{
                width: 224,
                height: 36,
                background: 'var(--th-surface)',
                border: '1px solid var(--th-border)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--th-text-faint)', flexShrink: 0 }}>
                <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.3" />
                <path
                  d="M10 10L13 13"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              </svg>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-transparent font-manrope text-[10px] font-medium tracking-widest outline-none th-placeholder"
                style={{ color: 'var(--th-text-muted)', letterSpacing: '1.4px' }}
                placeholder={translate('findDocument', 'ko')}
                aria-label="문서 검색"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  style={{ color: 'var(--th-text-faint)' }}
                >
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path
                      d="M1 1L9 9M9 1L1 9"
                      stroke="currentColor"
                      strokeWidth="1.3"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              )}
            </div>
            <ThemeToggle />
          </div>
        </header>

        {/* ── 캘린더 ───────────────────────────────── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* 요일 헤더 */}
          <div
            className="grid shrink-0 grid-cols-7"
            style={{ borderBottom: '1px solid var(--th-separator)' }}
          >
            {WEEKDAYS.map((day) => (
              <div
                key={day}
                className="flex items-center justify-center"
                style={{
                  height: 48,
                  borderRight: '1px solid var(--th-separator)',
                }}
              >
                <span
                  className="font-inter font-bold text-[10px] tracking-[2px]"
                  style={{ color: 'var(--th-text-muted)' }}
                >
                  {day}
                </span>
              </div>
            ))}
          </div>

          {/* 날짜 행 */}
          <div
            className="grid flex-1 overflow-hidden"
            style={{ gridTemplateRows: `repeat(${rows.length}, 1fr)` }}
          >
            {rows.map((row, rowIdx) => (
              <div
                key={rowIdx}
                className="grid grid-cols-7"
                style={{ borderBottom: '1px solid var(--th-separator)' }}
              >
                {row.map((cell, colIdx) => {
                  const todayCell = isToday(cell.date)
                  const events = getEvents(cell.date)
                  const highlighted = search ? matchesSearch(cell.date) : true
                  const dateKey = toKey(cell.date)
                  const isSelected = selectedDate === dateKey

                  return (
                    <div
                      key={colIdx}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleDayClick(cell.date)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') handleDayClick(cell.date)
                      }}
                      className="relative flex flex-col overflow-hidden transition-colors cursor-pointer"
                      style={{
                        borderRight: '1px solid var(--th-separator)',
                        background: isSelected
                          ? 'rgba(129,236,255,0.06)'
                          : todayCell
                            ? 'rgba(129,236,255,0.03)'
                            : 'transparent',
                        opacity: search && !highlighted ? 0.25 : 1,
                      }}
                    >
                      {/* 날짜 숫자 */}
                      <span
                        className="font-inter font-semibold text-sm"
                        style={{
                          padding: '16px 0 0 16px',
                          display: 'block',
                          color: todayCell
                            ? '#81ecff'
                            : cell.current
                              ? 'var(--th-text)'
                              : 'var(--th-text-faint)',
                        }}
                      >
                        {String(cell.date.getDate()).padStart(2, '0')}
                      </span>

                      {/* 이벤트 */}
                      {events.length > 0 && (
                        <div className="flex flex-col gap-1.5 px-4 pt-2">
                          {events.map((event, i) => (
                            <div key={i} className="flex flex-col gap-1">
                              <div
                                className="rounded-full"
                                style={{
                                  height: 4,
                                  width: 61,
                                  background: event.color,
                                  opacity: todayCell ? 1 : 0.6,
                                }}
                              />
                              <span
                                className="font-inter font-semibold truncate"
                                style={{
                                  fontSize: 8,
                                  letterSpacing: '1.6px',
                                  textTransform: 'uppercase',
                                  color: event.color,
                                  opacity: todayCell ? 1 : 0.6,
                                }}
                              >
                                {event.label}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* ── 일별 문서 패널 ────────────────────────── */}
      {dayPanelOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={handleDayPanelClose}
          />
          <aside
            className="fixed right-0 top-0 z-20 flex h-full flex-col overflow-hidden"
            style={{
              width: 320,
              background: 'var(--th-day-panel)',
              borderLeft: '1px solid var(--th-day-panel-border)',
            }}
          >
            <div
              className="flex shrink-0 items-center justify-between px-6"
              style={{
                height: 64,
                borderBottom: '1px solid var(--th-separator)',
              }}
            >
              <span
                className="font-inter font-semibold text-xs tracking-widest"
                style={{ color: '#81ecff' }}
              >
                {selectedDate ? formatDateLabel(selectedDate) : ''}
              </span>
              <button
                onClick={handleDayPanelClose}
                className="flex h-7 w-7 items-center justify-center rounded transition-opacity hover:opacity-70"
                style={{ color: 'var(--th-text-faint)' }}
                aria-label="닫기"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path
                    d="M1 1L11 11M11 1L1 11"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-4">
              {dayItems.length === 0 ? (
                <div
                  className="flex flex-1 items-center justify-center font-inter text-xs"
                  style={{ color: 'var(--th-text-faint)' }}
                >
                  문서 없음
                </div>
              ) : (
                dayItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => router.push(`/analysis/${item.id}`)}
                    className="flex flex-col gap-1.5 rounded-lg px-4 py-3 text-left transition-colors"
                    style={{ background: 'var(--th-separator)' }}
                  >
                    <span
                      className="font-inter text-xs font-medium leading-snug"
                      style={{ color: 'var(--th-text)' }}
                    >
                      {item.title}
                    </span>
                    <div className="flex items-center gap-2">
                      <span
                        className="rounded-full px-2 py-0.5 font-inter text-[9px] font-semibold uppercase tracking-widest"
                        style={{
                          background: `${getCategoryColor(item.category)}18`,
                          color: getCategoryColor(item.category),
                        }}
                      >
                        {item.category}
                      </span>
                      {item.deadline && (
                        <span
                          className="font-inter text-[9px]"
                          style={{ color: '#747579' }}
                        >
                          {item.deadline.slice(0, 10)}
                        </span>
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          </aside>
        </>
      )}

      {/* ── 업로드 토스트 ────────────────────────── */}
      {uploadToast.visible && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-full px-5 py-2.5 font-inter text-xs font-medium"
          style={{
            background: 'var(--th-surface-2, var(--th-surface))',
            border: '1px solid var(--th-border)',
            color: 'var(--th-text-muted)',
            backdropFilter: 'blur(8px)',
          }}
        >
          {uploadToast.fileName} 업로드 중…
        </div>
      )}

      <UploadModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onUpload={handleUpload}
      />

      <style>{`
        @media (max-width: 768px) {
          main {
            margin-left: 0 !important;
            padding-left: 12px !important;
            padding-right: 12px !important;
          }
          header {
            flex-direction: column !important;
            height: auto !important;
            padding: 16px 12px !important;
            gap: 12px !important;
            align-items: stretch !important;
          }
          header > div:first-child {
            justify-content: space-between !important;
            width: 100% !important;
          }
          header nav {
            overflow-x: auto !important;
            white-space: nowrap !important;
            padding-bottom: 6px !important;
            justify-content: flex-start !important;
            width: 100% !important;
            scrollbar-width: none;
          }
          header nav::-webkit-scrollbar {
            display: none;
          }
          header > div:last-child {
            width: 100% !important;
          }
          .grid-cols-7 > div {
            min-height: 54px !important;
          }
          .grid-cols-7 span {
            padding: 6px 0 0 6px !important;
            font-size: 11px !important;
          }
          aside {
            display: none !important;
          }
        }
      `}</style>
    </div>
  )
}
