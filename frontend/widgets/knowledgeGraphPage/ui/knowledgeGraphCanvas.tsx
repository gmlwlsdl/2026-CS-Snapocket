import React, { useCallback, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from 'react-force-graph-2d'
import type { GraphNode, GraphEdge } from '../knowledgeGraph.type'
import {
  NODE_COLOR,
  NODE_DOT_SIZE,
} from '../knowledgeGraph.constant'

interface KnowledgeGraphCanvasProps {
  searchTerm?: string
  matchedNodeIds?: string[] | null
  matchedScores?: Record<string, number> | null
  nodes: GraphNode[]
  edges: GraphEdge[]
  graphRef?: React.MutableRefObject<ForceGraphMethods<NodeObject<GraphNode>> | undefined>
}

export function KnowledgeGraphCanvas({
  searchTerm,
  matchedNodeIds,
  matchedScores,
  nodes,
  edges,
  graphRef,
}: KnowledgeGraphCanvasProps) {
  const router = useRouter()
  const containerRef = useRef<HTMLDivElement>(null)
  const matchedNodeIdSet = useMemo(() => new Set(matchedNodeIds ?? []), [matchedNodeIds])

  const getMatchStrength = useCallback(
    (node: NodeObject<GraphNode>) => {
      if (!searchTerm) return 1
      const normalizedScore = matchedScores?.[String(node.id)]
      if (normalizedScore !== undefined) {
        return normalizedScore
      }
      if (matchedNodeIds) {
        return matchedNodeIdSet.has(String(node.id)) ? 1 : 0
      }
      return node.label.toLowerCase().includes(searchTerm.toLowerCase()) ? 1 : 0
    },
    [matchedNodeIdSet, matchedNodeIds, matchedScores, searchTerm],
  )

  const graphData = useMemo(() => {
    const nodeIds = new Set(nodes.map((n) => n.id))

    const filteredLinks = edges
      .filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to))
      .map((e) => ({
        source: e.from,
        target: e.to,
      }))

    return { nodes, links: filteredLinks }
  }, [nodes, edges])

  const getNodeOpacity = useCallback(
    (strength: number) => {
      if (!searchTerm) return 1
      if (strength <= 0) return 0.14
      return 0.55 + strength * 0.45
    },
    [searchTerm],
  )

  const getGlowRadius = useCallback((baseRadius: number, strength: number, globalScale: number) => {
    return baseRadius * ((8 + strength * 10) * Math.pow(globalScale, -0.3))
  }, [])

  const drawNode = useCallback((node: NodeObject<GraphNode>, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const strength = getMatchStrength(node)
    const matched = strength > 0
    const normalizedStrength = Math.max(0, Math.min(1, strength))
    // 검색 점수가 높을수록 더 밝고 또렷하게 보여주고,
    // 비매칭 노드는 충분히 어둡게 내려서 대비를 만든다.
    const opacity = getNodeOpacity(normalizedStrength)
    const color = NODE_COLOR[node.category] ?? '#81ecff'
    const baseR = (NODE_DOT_SIZE[node.size] ?? 5) / globalScale

    if (matched) {
      ctx.save()

      const glowRadius = getGlowRadius(baseR, normalizedStrength, globalScale)

      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, glowRadius,
      )

      gradient.addColorStop(0, 'rgba(255, 255, 255, 1)')
      gradient.addColorStop(0.12, `rgba(129, 236, 255, ${0.5 + normalizedStrength * 0.4})`)
      gradient.addColorStop(0.3, `rgba(129, 236, 255, ${0.18 + normalizedStrength * 0.18})`)
      gradient.addColorStop(0.6, `rgba(129, 236, 255, ${0.03 + normalizedStrength * 0.04})`)
      gradient.addColorStop(1, 'rgba(129, 236, 255, 0)')

      ctx.beginPath()
      ctx.arc(node.x, node.y, glowRadius, 0, 2 * Math.PI, false)
      ctx.fillStyle = gradient
      ctx.globalAlpha = opacity
      ctx.fill()

      ctx.beginPath()
      ctx.arc(node.x, node.y, baseR + normalizedStrength * (2 / globalScale), 0, 2 * Math.PI, false)
      ctx.fillStyle = color
      ctx.globalAlpha = opacity
      ctx.fill()

      ctx.restore()
    } else {
      ctx.beginPath()
      ctx.arc(node.x, node.y, baseR, 0, 2 * Math.PI, false)
      ctx.fillStyle = color
      ctx.globalAlpha = opacity
      ctx.fill()
    }

    if (globalScale > 0.8) {
      const fontSize = (node.size === 'primary' ? 11 : 9) / globalScale
      ctx.font = `${node.size === 'primary' ? '500' : '400'} ${fontSize}px Inter`
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = matched ? '#f9f9fd' : '#aaabaf'
      ctx.fillText(node.label, node.x + baseR + 8 / globalScale, node.y)
    }

    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
  }, [getGlowRadius, getMatchStrength, getNodeOpacity])

  return (
    <div
      ref={containerRef}
      className="relative flex h-full w-full items-center justify-center overflow-hidden"
      style={{ background: '#0c0e11' }}
    >
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            'radial-gradient(ellipse 60% 60% at 50% 50%, rgba(23,26,29,0.8) 0%, transparent 100%)',
        }}
      />

      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeCanvasObject={drawNode}
        nodeLabel="label"
        linkColor={() => 'rgba(129,236,255,0.12)'}
        linkWidth={1}
        backgroundColor="transparent"
        onNodeClick={(node: NodeObject<GraphNode>) => {
          router.push(`/analysis/${node.id}`)
        }}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  )
}
