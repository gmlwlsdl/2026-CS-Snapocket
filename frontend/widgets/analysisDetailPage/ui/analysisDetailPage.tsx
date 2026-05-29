'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import {
  TextInput,
  Textarea,
  Select,
  Button,
  ActionIcon,
  Badge,
  Text,
  Group,
  Stack,
} from '@mantine/core'
import {
  apiFetchBlobUrl,
  fetchDocument,
  deleteDocument,
} from '@/entities/document'
import {
  confirmAnalysis,
  fetchAnalysisResult,
  fetchAnalysisStatus,
  retryAnalysis,
  isoToDisplay,
  displayToIso,
} from '@/entities/analysis'
import { t as translate } from '@/shared/lib/i18n'
import type { DocumentStatus } from '@/entities/document'
import { ApiError } from '@/shared/api'
import { useToast } from '@/shared/ui'
import { replaceDocumentTags } from '@/entities/tag'
import {CalendarBlankIcon, Clock} from '@phosphor-icons/react'

// ── 로컬 타입 ────────────────────────────────────────────────────────────────

type PageStatus = 'loading' | 'polling' | 'ready' | 'not-started' | 'failed' | 'saving' | 'discarding'

interface TagItem {
  id: number | string
  label: string
  color: string
}

interface FormState {
  title: string
  category: string
  captureDate: string
  summary: string
  tags: TagItem[]
  rawText: string
  keyConcepts: string[]
  deadline: string
  fileType: string
  fileUrl: string
  id: string
}

const CATEGORY_OPTIONS = ['lecture', 'assignment', 'notice', 'receipt', 'memo']

const POLL_INTERVAL_MS = 3_000

// ── 유틸 ─────────────────────────────────────────────────────────────────────

function todayDisplay(): string {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${m}/${day}/${d.getFullYear()}`
}

function tagColor(label: string): string {
  const colors = ['#97c2ec', '#ac89ff', '#fab0ff']
  const hash = label.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return colors[hash % colors.length]
}

function rawTagName(label: string): string {
  return label.startsWith('#') ? label.slice(1) : label
}

function normaliseTags(tags: string[]): TagItem[] {
  return tags.map((t, i) => ({
    id: i,
    label: t.startsWith('#') ? t : `#${t}`,
    color: tagColor(t),
  }))
}

// ── 컴포넌트 ──────────────────────────────────────────────────────────────────

export function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  const mode = searchParams.get('mode')

  const [pageStatus, setPageStatus] = useState<PageStatus>('loading')
  const [documentStatus, setDocumentStatus] = useState<DocumentStatus | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [form, setForm] = useState<FormState>({
    title: '',
    category: 'lecture',
    captureDate: todayDisplay(),
    summary: '',
    tags: [],
    rawText: '',
    keyConcepts: [],
    deadline: todayDisplay(),
    fileType: '',
    fileUrl: '',
    id: '',
  })

  const [addingTag, setAddingTag] = useState(false)
  const [newTag, setNewTag] = useState('')

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const imageBlobRef = useRef<string | null>(null)

  // ── 초기 로딩 ─────────────────────────────────────────────────────────────

  const loadResult = useCallback(async () => {
    try {
      const result = await fetchAnalysisResult(id)
      setForm({
        title: result.title,
        category: result.category || 'lecture',
        captureDate: isoToDisplay(result.capture_date) || todayDisplay(),
        summary: result.summary,
        tags: normaliseTags(result.tags),
        rawText: result.raw_text,
        keyConcepts: result.key_concepts,
        deadline: isoToDisplay(result.deadline) || todayDisplay(),
        fileType: result.file_type,
        fileUrl: result.file_url,
        id: result.id,
      })
      setDocumentStatus('analyzed')
      setPageStatus('ready')
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : '분석 결과 로드 실패')
      setPageStatus('failed')
    }
  }, [id])

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return
    setPageStatus('polling')
    pollTimerRef.current = setInterval(async () => {
      try {
        const statusData = await fetchAnalysisStatus(id)
        setDocumentStatus(statusData.status)
        if (statusData.status === 'analyzed') {
          clearInterval(pollTimerRef.current!)
          pollTimerRef.current = null
          await loadResult()
        } else if (statusData.status === 'failed') {
          clearInterval(pollTimerRef.current!)
          pollTimerRef.current = null
          setPageStatus('failed')
        }
      } catch { /* 다음 주기에 재시도 */ }
    }, POLL_INTERVAL_MS)
  }, [id, loadResult])

  useEffect(() => {
    if (!id) return
    let alive = true
    let blobUrl: string | null = null

    async function init() {
      setPageStatus('loading')
      setErrorMsg(null)

      if (mode === 'result') {
        await loadResult()
      } else {
        const [docResult, blobResult] = await Promise.allSettled([
          fetchDocument(id),
          apiFetchBlobUrl(`/documents/${id}/file`),
        ])
        if (!alive) return

        if (docResult.status === 'rejected') {
          const err = docResult.reason
          setErrorMsg(err instanceof ApiError ? err.message : '문서 로드 실패')
          setPageStatus('failed')
          return
        }

        const doc = docResult.value
        if (blobResult.status === 'fulfilled') {
          blobUrl = blobResult.value
          imageBlobRef.current = blobUrl
          setImageUrl(blobUrl)
        }

        setForm({
          title: doc.title,
          category: doc.category || 'lecture',
          captureDate: isoToDisplay(doc.capture_date) || todayDisplay(),
          summary: doc.summary,
          tags: normaliseTags(doc.tags),
          rawText: doc.raw_text,
          keyConcepts: doc.key_concepts,
          deadline: isoToDisplay(doc.deadline) || todayDisplay(),
          fileType: doc.file_type,
          fileUrl: doc.file_url,
          id: doc.id,
        })
        setDocumentStatus(doc.status)

        switch (doc.status) {
          case 'analyzed': setPageStatus('ready'); break
          case 'processing': startPolling(); break
          case 'uploaded': setPageStatus('not-started'); break
          case 'failed': setPageStatus('failed'); break
        }
      }
    }

    init()
    return () => {
      alive = false
      if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null }
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [id, loadResult, startPolling])

  // ── 액션 핸들러 ────────────────────────────────────────────────────────────

  async function handleConfirm() {
    if (form.captureDate && !/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(form.captureDate)) {
      toast.error('날짜 형식이 올바르지 않습니다. MM/DD/YYYY 형식으로 입력해 주세요.')
      return
    }
    setPageStatus('saving')
    try {
      await confirmAnalysis(id, {
        title: form.title,
        category: form.category,
        capture_date: displayToIso(form.captureDate),
        deadline: form.deadline ? displayToIso(form.deadline) : null,
        summary: form.summary,
        tags: form.tags.map((t) => rawTagName(t.label)),
      })
      router.push('/')
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : '저장 실패')
      setPageStatus('ready')
    }
  }

  async function handleRecalibrate() {
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null }
    try {
      await retryAnalysis(id)
      startPolling()
    } catch (e) {
      toast.error(e, '재분석 요청에 실패했습니다.')
    }
  }

  async function handleDiscard() {
    toast.runWithCountdown({
      title: '파일 삭제 예약',
      message: '이 알림을 닫으면 삭제가 취소됩니다.',
      actionLabel: '삭제',
      duration: 5000,
      color: 'red',
      onComplete: async () => {
        setPageStatus('discarding')
        try {
          await deleteDocument(id)
          router.push('/')
        } catch (e) {
          setErrorMsg(e instanceof ApiError ? e.message : '삭제 실패')
          setPageStatus('ready')
        }
      },
    })
  }

  async function handleAddTag() {
    const trimmed = newTag.trim()
    if (!trimmed) return
    const rawName = rawTagName(trimmed)
    if (form.tags.some((t) => rawTagName(t.label) === rawName)) {
      setNewTag(''); setAddingTag(false); return
    }
    try {
      const savedTags = await replaceDocumentTags(id, {
        tags: [...form.tags.map((t) => rawTagName(t.label)), rawName],
      })
      setForm((f) => ({
        ...f,
        tags: savedTags.map((t) => ({
          id: t.id,
          label: t.name.startsWith('#') ? t.name : `#${t.name}`,
          color: tagColor(t.name),
        })),
      }))
      toast.success('태그가 추가되었습니다.')
    } catch (err) {
      toast.error(err, '태그 추가에 실패했습니다.')
    } finally {
      setNewTag(''); setAddingTag(false)
    }
  }

  async function handleRemoveTag(tagId: number | string) {
    const remainingTagLabels = form.tags.filter((t) => t.id !== tagId).map((t) => rawTagName(t.label))
    try {
      const savedTags = await replaceDocumentTags(id, { tags: remainingTagLabels })
      setForm((f) => ({
        ...f,
        tags: savedTags.map((t) => ({
          id: t.id,
          label: t.name.startsWith('#') ? t.name : `#${t.name}`,
          color: tagColor(t.name),
        })),
      }))
      toast.success('태그가 삭제되었습니다.')
    } catch (err) {
      toast.error(err, '태그 삭제에 실패했습니다.')
    }
  }

  const isProcessing = pageStatus === 'loading' || pageStatus === 'polling'
  const isSaving = pageStatus === 'saving'
  const isDiscarding = pageStatus === 'discarding'
  const isInteractive = pageStatus === 'ready' && documentStatus === 'analyzed'

  // ── 렌더링 ────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden font-inter" style={{ background: 'var(--th-bg)' }}>
      {/* ── Top Header ─────────────────────────────────────────────────────── */}
      <header
        className="flex shrink-0 items-center justify-between px-8 h-[77px] backdrop-blur-md"
        style={{ background: 'var(--th-header-bg)', borderBottom: '1px solid var(--th-separator)' }}
      >
        <div className="flex items-center gap-4">
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            radius="md"
            onClick={() => router.back()}
            aria-label="뒤로 가기"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 3L5 8L10 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </ActionIcon>

          <div className="flex flex-col">
            <Text fw={800} size="xl" ff="var(--font-manrope), Manrope, sans-serif" style={{ letterSpacing: '-0.5px' }}>
              {translate('analysisDetail', 'ko')}
            </Text>
            <div className="flex items-center gap-2">
              <span className={`inline-block rounded-full w-2 h-2 ${isProcessing ? 'bg-amber-500' : pageStatus === 'failed' ? 'bg-red-600' : 'bg-snap-cyan'}`} />
              <Text size="xs" c="dimmed" style={{ letterSpacing: '1.2px' }}>
                {isProcessing ? translate('analyzing', 'ko')
                  : pageStatus === 'failed' ? translate('analysisFailed', 'ko')
                  : isSaving ? translate('saving', 'ko')
                  : translate('editingExtractedData', 'ko')}
              </Text>
            </div>
          </div>
        </div>

        <Button
          onClick={handleConfirm}
          disabled={!isInteractive || isSaving}
          radius="xl"
          w={184}
          h={44}
          style={{ background: 'linear-gradient(135deg, #97c2ec 0%, #97c2ec 100%)', color: '#0d2b45', fontWeight: 700 }}
        >
          {isSaving ? translate('saving', 'ko') : translate('confirmSave', 'ko')}
        </Button>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <main className="flex flex-1 gap-12 overflow-hidden px-8 py-8">
        {/* ── Left Panel ───────────────────────────────────────────────────── */}
        <div className="flex w-[38.4%] shrink-0 flex-col gap-4">
          <div className="relative flex-1 overflow-hidden rounded-xl bg-black min-h-0" style={{ border: '1px solid var(--th-border)' }}>
            {imageUrl
              ? <img src={imageUrl} alt="Original document" className="absolute inset-0 h-full w-full object-contain" />
              : <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 30% 40%, rgba(0,180,210,0.07) 0%, transparent 60%), radial-gradient(ellipse at 70% 70%, rgba(172,137,255,0.05) 0%, transparent 60%)' }} />
            }
            {isProcessing && (
              <>
                <div className="pointer-events-none absolute left-0 right-0 top-0 h-[2px] bg-snap-cyan/40" style={{ animation: 'scan-line 2.4s linear infinite' }} />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                  <div className="h-8 w-8 rounded-full border-2 border-snap-cyan/20 border-t-snap-cyan" style={{ animation: 'spin 0.9s linear infinite' }} />
                  <span className="text-[11px] font-semibold tracking-[2px] text-snap-cyan/50">
                    {pageStatus === 'polling' ? 'ANALYZING…' : 'LOADING…'}
                  </span>
                </div>
              </>
            )}
            {pageStatus === 'failed' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                <span className="text-[11px] font-semibold tracking-[2px] text-red-600">ANALYSIS FAILED</span>
                {errorMsg && <span className="text-[10px] text-red-600/60 max-w-[80%] text-center">{errorMsg}</span>}
              </div>
            )}
            <style>{`
              @keyframes scan-line { 0% { top:0%;opacity:1} 80%{opacity:1} 100%{top:100%;opacity:0} }
              @keyframes spin { to { transform: rotate(360deg) } }
            `}</style>
          </div>

          <Group gap="xs">
            <Button
              variant="default"
              flex={1}
              h={48}
              radius="md"
              disabled={isProcessing || isSaving || isDiscarding}
              onClick={handleRecalibrate}
            >
              <Text size="xs" style={{ letterSpacing: '1.2px' }}>{translate('recalibrateAiLens', 'ko')}</Text>
            </Button>
            {/* <ActionIcon variant="default" size={48} radius="md" disabled aria-label="설정">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.4" opacity="0.5" />
                <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.5" />
              </svg>
            </ActionIcon> */}
          </Group>
        </div>

        {/* ── Right Panel ──────────────────────────────────────────────────── */}
        <Stack flex={1} gap="lg" style={{ overflowY: 'auto', minWidth: 0 }}>
          {/* Document Title */}
          <Stack gap={6}>
            <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
              {translate('documentTitle', 'ko')}
            </Text>
            <TextInput
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              disabled={!isInteractive}
              placeholder={isProcessing ? 'Analyzing…' : '문서 제목'}
              styles={{
                input: {
                  fontSize: 32,
                  fontWeight: 600,
                  height: 'auto',
                  paddingTop: 14,
                  paddingBottom: 14,
                  lineHeight: 1.25,
                  fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                },
              }}
            />
          </Stack>

          {/* Category + Dates */}
          <Group gap="xl" align="flex-end">
            <Stack gap={6} flex={1}>
              <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
                {translate('category', 'ko')}
              </Text>
              <Select
                data={CATEGORY_OPTIONS}
                value={form.category}
                onChange={(v) => v && setForm((f) => ({ ...f, category: v }))}
                disabled={!isInteractive}
                allowDeselect={false}
              />
            </Stack>

            <Stack gap={6} flex={1}>
              <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
                {translate('captureDate', 'ko')}
              </Text>
              <TextInput
                value={form.captureDate}
                onChange={(e) => setForm((f) => ({ ...f, captureDate: e.target.value }))}
                disabled={!isInteractive}
                placeholder="MM/DD/YYYY"
                rightSection={
                  <CalendarBlankIcon size={20} color="#868e96" />
                }
              />
            </Stack>

            <Stack gap={6} flex={1}>
              <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
                {translate('deadline', 'ko')}
              </Text>
              <TextInput
                value={form.deadline}
                onChange={(e) => setForm((f) => ({ ...f, deadline: e.target.value }))}
                disabled={!isInteractive}
                placeholder="MM/DD/YYYY"
                rightSection={
                  <Clock size={20} color={'#868e96'}/>
                }
              />
            </Stack>
          </Group>

          {/* Content Summary */}
          <Stack gap={8}>
            <Group justify="space-between">
              <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
                {translate('contentSummary', 'ko')}
              </Text>
              <Badge color="snap" variant="light" size="xs">AI Generated</Badge>
            </Group>
            <Textarea
              value={form.summary}
              onChange={(e) => setForm((f) => ({ ...f, summary: e.target.value }))}
              disabled={!isInteractive}
              placeholder={isProcessing ? translate('analyzing', 'ko') : ''}
              minRows={9}
              autosize
            />
          </Stack>

          {/* Key Concepts */}
          {mode === 'result' && (
            <Stack gap={8}>
              <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
                {translate('keyConcepts', 'ko')}
              </Text>
              <Group gap="xs">
                {form.keyConcepts.length > 0
                  ? form.keyConcepts.map((concept, idx) => (
                      <Badge key={idx} color="snap" variant="light" radius="xl">{concept}</Badge>
                    ))
                  : <Text size="xs" c="dimmed" fs="italic">{isProcessing ? 'Extracting concepts…' : 'No concepts extracted'}</Text>
                }
              </Group>
            </Stack>
          )}

          {/* Raw Text */}
          <Stack gap={8}>
            <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
              {translate('rawText', 'ko')}
            </Text>
            <Textarea
              readOnly
              value={form.rawText}
              placeholder={isProcessing ? 'Extracting text…' : 'No text available'}
              minRows={7}
              styles={{ input: { opacity: 0.5 } }}
            />
          </Stack>

          {/* Knowledge Tags */}
          <Stack gap={8}>
            <Text size="xs" c="dimmed" style={{ letterSpacing: '2px', textTransform: 'uppercase' }}>
              {translate('tags', 'ko')}
            </Text>
            <Group gap="xs" align="center">
              {form.tags.map((tag) => (
                <div
                  key={tag.id}
                  className="group flex items-center gap-1 rounded-md px-3 py-1"
                  style={{ background: 'var(--th-surface)', border: `1px solid ${tag.color}33` }}
                >
                  <span className="text-[12px] font-bold" style={{ color: tag.color }}>{tag.label}</span>
                  {isInteractive && (
                    <button
                      onClick={() => handleRemoveTag(tag.id)}
                      className="ml-0.5 opacity-0 transition-opacity group-hover:opacity-60"
                      aria-label="태그 제거"
                    >
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 2L8 8M8 2L2 8" stroke={tag.color} strokeWidth="1.3" strokeLinecap="round" />
                      </svg>
                    </button>
                  )}
                </div>
              ))}

              {isInteractive && (
                addingTag
                  ? <input
                      autoFocus
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleAddTag(); if (e.key === 'Escape') setAddingTag(false) }}
                      onBlur={handleAddTag}
                      className="rounded-md px-3 outline-none h-[26px] border border-snap-cyan/30 text-[12px] font-bold text-snap-cyan w-[100px]"
                      style={{ background: 'var(--th-surface)' }}
                      placeholder="#tag"
                    />
                  : <Button variant="subtle" color="gray" size="xs" radius="md" onClick={() => setAddingTag(true)}>
                      {translate('addTag', 'ko')}
                    </Button>
              )}
            </Group>
          </Stack>

          {/* Footer — Discard */}
          <div className="mt-auto pt-6" style={{ borderTop: '1px solid var(--th-separator)' }}>
            <Button
              variant="subtle"
              color="red"
              leftSection={
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 4H14M5 4V2.5C5 2 5.5 1.5 6 1.5H10C10.5 1.5 11 2 11 2.5V4M6.5 7V12M9.5 7V12M3.5 4L4.5 13.5C4.5 14 5 14.5 5.5 14.5H10.5C11 14.5 11.5 14 11.5 13.5L12.5 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              }
              disabled={isDiscarding || isSaving}
              onClick={handleDiscard}
            >
              {isDiscarding ? translate('discarding', 'ko') : translate('discardExtraction', 'ko')}
            </Button>
          </div>
        </Stack>
      </main>
    </div>
  )
}
