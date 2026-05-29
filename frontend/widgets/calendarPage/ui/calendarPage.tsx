'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { SidebarNav, useToast } from '@/shared/ui'
import { UploadModal } from '@/features/upload'
import {
  fetchCalendarMonth,
  fetchCalendarDay,
  type CalendarDates,
  type CalendarDayItem,
} from '@/entities/calendar'

import { TopHeader } from '@/widgets/knowledgeGraphPage/ui/topHeader'
import type { CategoryFilter } from '@/widgets/knowledgeGraphPage/knowledgeGraph.type'
import { CaretLeftIcon, CaretRightIcon } from '@phosphor-icons/react'

const WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일']

const MONTH_NAMES = [
  '1월', '2월', '3월', '4월', '5월', '6월',
  '7월', '8월', '9월', '10월', '11월', '12월',
]

const CATEGORY_COLOR: Record<string, string> = {
  lecture: '#ac89ff',
  assignment: '#97c2ec',
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
  const { toast } = useToast()
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [search] = useState('')
  const [activeFilter, setActiveFilter] = useState<CategoryFilter>('all')
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
      toast.error('파일 업로드에 실패했습니다. 다시 시도해 주세요.')
      setUploadToast({ visible: false, fileName: '' })
    }
  }, [router, toast])

  return (
    <div
      className="flex h-screen w-full overflow-hidden"
      style={{ background: 'var(--th-bg)' }}
    >
      <SidebarNav onUpload={() => setModalOpen(true)} />

      <main
        className="flex flex-1 flex-col overflow-hidden pt-16"
        style={{ marginLeft: 81 }}
      >
        {/* ── 헤더 ─────────────────────────────────── */}
        <TopHeader
          activeFilter={activeFilter}
          onFilterChange={(v) => setActiveFilter(v)}
          // summaryData={summaryData}
        />
        <div
          className="calendar-month-toolbar flex h-16 shrink-0 items-center justify-center gap-5 px-8"
          style={{ borderBottom: '1px solid var(--th-separator)' }}
        >
          <button
            onClick={prevMonth}
            className="calendar-month-button flex h-9 w-9 items-center justify-center rounded-full transition-all"
            aria-label="이전 달"
            style={{ color: 'var(--th-text-muted)' }}
          >
            <CaretLeftIcon size={18} weight="bold" />
          </button>

          <div className="flex min-w-[152px] items-baseline justify-center gap-2">
            <span
              className="font-manrope text-2xl font-extrabold"
              style={{ color: 'var(--th-text)', letterSpacing: '-0.4px' }}
            >
              {MONTH_NAMES[month]}
            </span>
            <span
              className="font-manrope text-sm font-bold"
              style={{ color: '#97c2ec', letterSpacing: '0.8px' }}
            >
              {year}
            </span>
          </div>

          <button
            onClick={nextMonth}
            className="calendar-month-button flex h-9 w-9 items-center justify-center rounded-full transition-all"
            aria-label="다음 달"
            style={{ color: 'var(--th-text-muted)' }}
          >
            <CaretRightIcon size={18} weight="bold" />
          </button>
        </div>

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
                            ? '#97c2ec'
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
            className="calendar-day-panel-backdrop fixed inset-0 z-10"
            onClick={handleDayPanelClose}
          />
          <aside
            className="calendar-day-panel fixed right-0 top-0 z-20 flex h-full flex-col overflow-hidden"
            style={{
              width: 360,
              background: 'var(--th-day-panel)',
              borderLeft: '1px solid var(--th-day-panel-border)',
            }}
          >
            <div
              className="flex shrink-0 items-center justify-between px-6"
              style={{
                height: 72,
                borderBottom: '1px solid var(--th-separator)',
              }}
            >
              <div className="flex flex-col gap-1">
                <span
                  className="font-inter text-[10px] font-bold uppercase tracking-[2px]"
                  style={{ color: '#97c2ec' }}
                >
                  Selected Date
                </span>
                <span
                  className="font-manrope text-base font-extrabold"
                  style={{ color: 'var(--th-text)', letterSpacing: '-0.4px' }}
                >
                  {selectedDate ? formatDateLabel(selectedDate) : ''}
                </span>
              </div>
              <button
                onClick={handleDayPanelClose}
                className="calendar-day-panel-close flex h-8 w-8 items-center justify-center rounded-full transition-all"
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

            <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-5">
              {dayItems.length === 0 ? (
                <div
                  className="calendar-day-empty flex flex-1 flex-col items-center justify-center gap-2 rounded-2xl px-6 text-center font-inter"
                >
                  <span
                    className="font-manrope text-sm font-bold"
                    style={{ color: 'var(--th-text)' }}
                  >
                    문서 없음
                  </span>
                  <span className="text-xs leading-5" style={{ color: 'var(--th-text-faint)' }}>
                    이 날짜에 연결된 문서가 없습니다.
                  </span>
                </div>
              ) : (
                dayItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => router.push(`/analysis/${item.id}`)}
                    className="calendar-day-card flex flex-col gap-3 rounded-xl px-4 py-4 text-left transition-all"
                  >
                    <span
                      className="font-inter text-sm font-semibold leading-snug"
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
                          className="font-inter text-[10px] font-medium"
                          style={{ color: 'var(--th-text-faint)' }}
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
        .calendar-day-panel-backdrop {
          background: rgba(15, 23, 42, 0.12);
          backdrop-filter: blur(2px);
          animation: calendar-backdrop-in 180ms ease-out;
        }

        .calendar-day-panel {
          box-shadow: -18px 0 48px rgba(15, 23, 42, 0.12);
          animation: calendar-panel-in 220ms cubic-bezier(0.22, 1, 0.36, 1);
        }

        .calendar-day-panel-close {
          background: rgba(151, 194, 236, 0.08);
        }

        .calendar-day-panel-close:hover {
          background: rgba(151, 194, 236, 0.18);
          color: #97c2ec !important;
          transform: rotate(90deg);
        }

        .calendar-day-panel-close:focus-visible {
          outline: 2px solid rgba(151, 194, 236, 0.72);
          outline-offset: 2px;
        }

        .calendar-day-card {
          background: var(--th-day-panel-card);
          border: 1px solid var(--th-day-panel-card-border);
          box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }

        .calendar-day-card:hover {
          border-color: rgba(151, 194, 236, 0.55);
          box-shadow: 0 14px 32px rgba(151, 194, 236, 0.18);
          transform: translateX(-3px);
        }

        .calendar-day-card:active {
          transform: translateX(-1px) scale(0.99);
        }

        .calendar-day-card:focus-visible {
          outline: 2px solid rgba(151, 194, 236, 0.72);
          outline-offset: 2px;
        }

        .calendar-day-empty {
          background: var(--th-day-panel-card);
          // border: 1px dashed var(--th-day-panel-card-border);
        }

        @keyframes calendar-panel-in {
          from {
            opacity: 0;
            transform: translateX(24px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        @keyframes calendar-backdrop-in {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        .calendar-month-button {
          background: transparent;
        }

        .calendar-month-button:hover {
          background: rgba(151, 194, 236, 0.1);
          color: #97c2ec !important;
          transform: translateY(-1px);
        }

        .calendar-month-button:focus-visible {
          outline: 2px solid rgba(151, 194, 236, 0.72);
          outline-offset: 2px;
        }

        @media (max-width: 768px) {
          main {
            margin-left: 0 !important;
            padding-left: 12px !important;
            padding-right: 12px !important;
            padding-top: 120px !important;
          }
          .calendar-month-toolbar {
            height: 56px !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
            gap: 12px !important;
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
          aside:not(.calendar-day-panel) {
            display: none !important;
          }
          .calendar-day-panel {
            top: auto !important;
            bottom: 0 !important;
            right: 0 !important;
            display: flex !important;
            width: 100% !important;
            height: 72vh !important;
            border-left: 0 !important;
            border-top: 1px solid var(--th-day-panel-border) !important;
            border-radius: 20px 20px 0 0;
            animation-name: calendar-panel-up-in;
          }
          .calendar-day-panel-backdrop {
            display: block !important;
          }
          @keyframes calendar-panel-up-in {
            from {
              opacity: 0;
              transform: translateY(24px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        }
      `}</style>
    </div>
  )
}
