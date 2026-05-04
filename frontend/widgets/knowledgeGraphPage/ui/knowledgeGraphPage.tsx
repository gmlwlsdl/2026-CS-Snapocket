'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import type {
  CategoryFilter,
  GraphNode,
  GraphEdge,
} from '../knowledgeGraph.type'
import {
  getNodes,
  getGraphSummary,
  type GraphSummaryData,
} from '@/entities/graph'
import { getSearchStatus, queryDocuments } from '@/entities/search'
import { CATEGORY_TO_NODE_CATEGORY } from '../knowledgeGraph.utils'
import dynamic from 'next/dynamic'
import { SidebarNav, ToastStatus, type ToastItem } from '@/shared/ui'
import { UploadModal } from '@/features/upload'
import { fetchAnalysisStatus } from '@/entities/analysis'
import { TopHeader } from './topHeader'
import type { ForceGraphMethods, NodeObject } from 'react-force-graph-2d'

const KnowledgeGraphCanvas = dynamic(
  () =>
    import('./knowledgeGraphCanvas').then((mod) => mod.KnowledgeGraphCanvas),
  { ssr: false },
)

import { GraphControls } from './graphControls'
import { AiInputBar } from './aiInputBar'

export function KnowledgeGraphPage() {
  const router = useRouter()
  const [activeFilter, setActiveFilter] = useState<CategoryFilter>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [matchedNodeIds, setMatchedNodeIds] = useState<string[] | null>(null)
  const [matchedScores, setMatchedScores] = useState<Record<string, number> | null>(null)
  const [aiAvailable, setAiAvailable] = useState(false)
  const [modeUsed, setModeUsed] = useState<'text' | 'semantic' | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [toastItems, setToastItems] = useState<ToastItem[]>([
    {
      id: 'test-error',
      fileName: 'lecture_note_week12.pdf',
      status: 'error',
      analysisId: 'test-error',
    },
  ])
  const [summaryData, setSummaryData] = useState<GraphSummaryData>()

  const graphRef = useRef<ForceGraphMethods<NodeObject<GraphNode>> | undefined>(
    undefined,
  )

  const clearSearchState = useCallback(() => {
    setMatchedNodeIds(null)
    setMatchedScores(null)
    setModeUsed(null)
  }, [])

  const handleZoomIn = useCallback(() => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom()
      graphRef.current.zoom(currentZoom * 1.2, 400)
    }
  }, [])

  const handleZoomOut = useCallback(() => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom()
      graphRef.current.zoom(currentZoom * 0.8, 400)
    }
  }, [])

  const handleFit = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(600, 80)
    }
  }, [])

  const applySearchResults = useCallback(
    (
      items: { id: string; score?: number | null }[],
      nextMode: 'text' | 'semantic',
      nextAiAvailable: boolean,
    ) => {
      setModeUsed(nextMode)
      setAiAvailable(nextAiAvailable)
      setMatchedNodeIds(items.map((item) => item.id))
      setMatchedScores(
        items.reduce<Record<string, number>>((acc, item) => {
          acc[item.id] = Math.max(0, Math.min(1, item.score ?? 0))
          return acc
        }, {}),
      )
    },
    [],
  )

  const loadAiAvailability = useCallback(async () => {
    try {
      const status = await getSearchStatus()
      setAiAvailable(status.aiAvailable)
    } catch (err) {
      console.error('Failed to load search status:', err)
    }
  }, [])

  const runTextSearch = useCallback(
    async (keyword: string) => {
      const response = await queryDocuments({
        keyword,
        mode: 'text',
        category: activeFilter === 'all' ? undefined : activeFilter,
        size: 50,
      })
      applySearchResults(response.items, response.modeUsed, response.aiAvailable)
    },
    [activeFilter, applySearchResults],
  )

  const runAutoSearch = useCallback(
    async (keyword: string) => {
      const response = await queryDocuments({
        keyword,
        mode: 'auto',
        category: activeFilter === 'all' ? undefined : activeFilter,
        size: 50,
      })
      applySearchResults(response.items, response.modeUsed, response.aiAvailable)
    },
    [activeFilter, applySearchResults],
  )

  useEffect(() => {
    getGraphSummary()
      .then(setSummaryData)
      .catch((err) => console.error('Failed to load graph summary:', err))

    loadAiAvailability()
  }, [loadAiAvailability])

  useEffect(() => {
    const controller = new AbortController()

    async function loadNodes() {
      const categoryMap: Record<CategoryFilter, string | undefined> = {
        all: undefined,
        lecture: 'lecture',
        assignment: 'assignment',
        notice: 'notice',
        receipt: 'receipt',
        memo: 'memo',
      }

      try {
        const apiNodes = await getNodes(categoryMap[activeFilter])

        if (!controller.signal.aborted) {
          const mappedNodes: GraphNode[] = apiNodes.map((n) => ({
            id: n.id,
            label: n.title,
            x: 0,
            y: 0,
            category: CATEGORY_TO_NODE_CATEGORY[n.category] ?? 'misc',
            size: n.connectionCount > 2 ? 'primary' : 'secondary',
          }))

          setNodes(mappedNodes)

          if (mappedNodes.length > 1) {
            const mockEdges: GraphEdge[] = mappedNodes
              .slice(0, -1)
              .map((n, i) => ({
                from: n.id,
                to: mappedNodes[i + 1].id,
              }))
            setEdges(mockEdges)
          } else {
            setEdges([])
          }
        }
      } catch (error) {
        console.error('Failed to load graph data:', error)
      }
    }

    loadNodes()

    return () => controller.abort()
  }, [activeFilter])

  useEffect(() => {
    const normalizedKeyword = searchTerm.trim()
    if (!normalizedKeyword) {
      clearSearchState()
      return
    }

    // 입력 중에는 빠른 텍스트 검색으로 즉시 반응성을 유지한다.
    const timer = setTimeout(async () => {
      try {
        await runTextSearch(normalizedKeyword)
      } catch (error) {
        console.error('Failed to run text search:', error)
      }
    }, 200)

    return () => clearTimeout(timer)
  }, [clearSearchState, runTextSearch, searchTerm])

  useEffect(() => {
    const processing = toastItems.filter((i) => i.status === 'processing')
    if (processing.length === 0) return

    const timers = processing.map((item) =>
      setInterval(async () => {
        try {
          const { status } = await fetchAnalysisStatus(item.id)
          if (status === 'analyzed') {
            setToastItems((prev) =>
              prev.map((i) =>
                i.id === item.id ? { ...i, status: 'complete' } : i,
              ),
            )
          } else if (status === 'failed') {
            setToastItems((prev) =>
              prev.map((i) =>
                i.id === item.id ? { ...i, status: 'error' } : i,
              ),
            )
          }
        } catch {
          setToastItems((prev) =>
            prev.map((i) => (i.id === item.id ? { ...i, status: 'error' } : i)),
          )
        }
      }, 3000),
    )

    return () => timers.forEach(clearInterval)
  }, [toastItems])

  const handleToastCancel = useCallback((item: ToastItem) => {
    setToastItems((prev) => prev.filter((i) => i.id !== item.id))
  }, [])

  const handleUpload = useCallback(async (file: File) => {
    const { uploadDocument } = await import('@/entities/document')

    try {
      const uploadRes = await uploadDocument(file)
      const documentId = uploadRes.document_id

      setToastItems((prev) => [
        {
          id: documentId,
          fileName: file.name,
          status: 'processing',
          analysisId: documentId,
        },
        ...prev,
      ])
    } catch (error) {
      console.error('Upload failed:', error)
    }
  }, [])

  const handleToastClick = useCallback(
    (item: ToastItem) => {
      if (item.status === 'complete') {
        router.push(`/analysis/${item.analysisId}?mode=result`)
      }
    },
    [router],
  )

  const handleSemanticSearch = useCallback(async () => {
    const normalizedKeyword = searchTerm.trim()
    if (!normalizedKeyword) {
      clearSearchState()
      return
    }

    setIsSearching(true)
    try {
      // Enter/버튼 시에는 AI 상태를 반영한 auto 검색을 호출한다.
      await runAutoSearch(normalizedKeyword)
    } catch (error) {
      console.error('Failed to run semantic search:', error)
      await loadAiAvailability()
    } finally {
      setIsSearching(false)
    }
  }, [clearSearchState, loadAiAvailability, runAutoSearch, searchTerm])

  return (
    <div className="flex h-screen w-full overflow-hidden bg-snap-bg">
      <SidebarNav onUpload={() => setModalOpen(true)} />

      <main className="relative flex-1" style={{ marginLeft: 81 }}>
        <TopHeader
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
          summaryData={summaryData}
        />

        <div className="absolute inset-0">
          <KnowledgeGraphCanvas
            searchTerm={searchTerm}
            matchedNodeIds={matchedNodeIds}
            matchedScores={matchedScores}
            nodes={nodes}
            edges={edges}
            graphRef={graphRef}
          />
        </div>

        <GraphControls
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFit={handleFit}
        />
        <AiInputBar
          value={searchTerm}
          aiAvailable={aiAvailable}
          modeUsed={modeUsed}
          isSearching={isSearching}
          onValueChange={setSearchTerm}
          onSubmitSearch={handleSemanticSearch}
        />
        <ToastStatus
          items={toastItems}
          onItemClick={handleToastClick}
          onCancel={handleToastCancel}
        />
      </main>

      <UploadModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onUpload={handleUpload}
      />
    </div>
  )
}
