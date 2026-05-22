import React, { useCallback, useEffect, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from 'react-force-graph-2d'
import type { GraphNode, GraphEdge, GraphEdgeType, NodeSize } from '../knowledgeGraph.type'
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

type GraphLink = {
  source: string
  target: string
  weight: number
  type: GraphEdgeType
}

type ClusterMember = {
  id: string
  depth: number
  parentId?: string
}

const ORPHAN_RING_RADIUS = 620
const CLUSTER_RING_RADIUS = 280
const CHILD_RING_BASE = 74
const GRANDCHILD_RING_BASE = 48
const SEARCH_GLOW_FLOOR = 0.18
const FORCE_LINK_DISTANCE = {
  parentMin: 82,
  parentMax: 138,
  similarMin: 68,
  similarMax: 230,
  relatedMin: 96,
  relatedMax: 270,
}
const FORCE_LINK_STRENGTH = {
  parentBase: 0.1,
  semanticBase: 0.026,
}

type D3LinkForce = {
  distance?: (distance: number | ((link: GraphLink) => number)) => D3LinkForce
  strength?: (strength: number | ((link: GraphLink) => number)) => D3LinkForce
  iterations?: (iterations: number) => D3LinkForce
}

type D3ChargeForce = {
  strength?: (strength: number | ((node: NodeObject<GraphNode>) => number)) => D3ChargeForce
  distanceMin?: (distance: number) => D3ChargeForce
  distanceMax?: (distance: number) => D3ChargeForce
  theta?: (theta: number) => D3ChargeForce
}

type D3CenterForce = {
  strength?: (strength: number) => D3CenterForce
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value))
}

function smoothstep(value: number) {
  const t = clamp01(value)
  return t * t * (3 - 2 * t)
}

function getVisualMatchStrength(score: number) {
  const raw = clamp01(score)
  if (raw <= 0) return 0

  const lifted = smoothstep((raw - SEARCH_GLOW_FLOOR) / (1 - SEARCH_GLOW_FLOOR))
  return clamp01(raw * 0.16 + lifted * 0.84)
}

function getSimilarityTension(weight: number) {
  return smoothstep(clamp01(weight))
}

function getWeightedLinkDistance(link: Partial<GraphLink>) {
  const tension = getSimilarityTension(Number(link.weight ?? 0))
  if (link.type === 'parent_of') {
    return FORCE_LINK_DISTANCE.parentMax
      - (FORCE_LINK_DISTANCE.parentMax - FORCE_LINK_DISTANCE.parentMin) * tension
  }
  if (link.type === 'similar_to') {
    return FORCE_LINK_DISTANCE.similarMax
      - (FORCE_LINK_DISTANCE.similarMax - FORCE_LINK_DISTANCE.similarMin) * tension
  }
  return FORCE_LINK_DISTANCE.relatedMax
    - (FORCE_LINK_DISTANCE.relatedMax - FORCE_LINK_DISTANCE.relatedMin) * tension
}

function getWeightedLinkStrength(link: Partial<GraphLink>) {
  const tension = getSimilarityTension(Number(link.weight ?? 0))
  if (link.type === 'parent_of') {
    return FORCE_LINK_STRENGTH.parentBase + tension * 0.18
  }
  return FORCE_LINK_STRENGTH.semanticBase + tension * 0.07
}

function getNodeRepelStrength(node: NodeObject<GraphNode>) {
  const sizeRepel = node.size === 'root' ? 760 : node.size === 'primary' ? 520 : 360
  const depthRelief = Math.min(120, Math.max(0, Number(node.depth ?? 2)) * 36)
  const orphanBoost = Number(node.connectionCount ?? 0) <= 0 ? 180 : 0
  return -(sizeRepel + orphanBoost - depthRelief)
}

function hashString(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

function uniqueByNodePair(edges: GraphEdge[]) {
  const seen = new Set<string>()
  return edges.filter((edge) => {
    const key = [edge.from, edge.to].sort().join(':')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}


function getSemanticNodeSize(node: GraphNode): NodeSize {
  const count = Number(node.connectionCount ?? 0)
  if (count >= 18) return 'root'
  if (count >= 3) return 'primary'
  return 'secondary'
}

function selectVisibleLinks(nodes: GraphNode[], edges: GraphEdge[]) {
  const nodeIds = new Set(nodes.map((node) => node.id))
  const validEdges = uniqueByNodePair(
    edges.filter((edge) => nodeIds.has(edge.from) && nodeIds.has(edge.to)),
  )
  const parentLinks = validEdges
    .filter((edge) => edge.type === 'parent_of')
    .map((edge) => ({
      source: edge.from,
      target: edge.to,
      weight: edge.weight,
      type: edge.type,
    }))

  const sparseAuxiliaryLinks = validEdges
    .filter((edge) => edge.type !== 'parent_of' && edge.weight >= 0.64)
    .sort((a, b) => b.weight - a.weight)
    .map((edge) => ({
      source: edge.from,
      target: edge.to,
      weight: edge.weight,
      type: edge.type,
    }))

  return [...parentLinks, ...sparseAuxiliaryLinks]
}

function computeHierarchyLayout(nodes: GraphNode[], links: GraphLink[]) {
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const childrenByParent = new Map<string, string[]>()
  const incomingParentCount = new Map<string, number>()
  const parentLinks = links.filter((link) => link.type === 'parent_of')

  parentLinks.forEach((link) => {
    const children = childrenByParent.get(link.source) ?? []
    children.push(link.target)
    childrenByParent.set(link.source, children)
    incomingParentCount.set(link.target, (incomingParentCount.get(link.target) ?? 0) + 1)
  })

  const rootIds = [...childrenByParent.keys()]
    .filter((id) => !incomingParentCount.has(id))
    .sort((a, b) => {
      const aChildren = childrenByParent.get(a)?.length ?? 0
      const bChildren = childrenByParent.get(b)?.length ?? 0
      return bChildren - aChildren || nodesById.get(a)!.label.localeCompare(nodesById.get(b)!.label)
    })

  const visited = new Set<string>()
  const clusters: { rootId: string; members: ClusterMember[] }[] = []

  rootIds.forEach((rootId) => {
    const queue: ClusterMember[] = [{ id: rootId, depth: 0 }]
    const members: ClusterMember[] = []
    while (queue.length > 0) {
      const item = queue.shift()!
      if (visited.has(item.id)) continue
      visited.add(item.id)
      members.push(item)
      ;(childrenByParent.get(item.id) ?? []).forEach((childId) => {
        queue.push({ id: childId, depth: item.depth + 1, parentId: item.id })
      })
    }
    if (members.length > 0) {
      clusters.push({ rootId, members })
    }
  })

  const orphanGroups = new Map<string, string[]>()
  nodes.forEach((node) => {
    if (visited.has(node.id)) return
    const key = `orphan:${node.category}`
    orphanGroups.set(key, [...(orphanGroups.get(key) ?? []), node.id])
  })

  const positioned = new Map<string, GraphNode>()
  const clusterCount = Math.max(1, clusters.length)
  clusters.forEach((cluster, index) => {
    const angle = (index / clusterCount) * Math.PI * 2 - Math.PI / 2
    const centerRadius = clusters.length === 1 ? 0 : CLUSTER_RING_RADIUS + Math.min(220, cluster.members.length * 10)
    const cx = Math.cos(angle) * centerRadius
    const cy = Math.sin(angle) * centerRadius * 0.72
    const root = nodesById.get(cluster.rootId)
    if (!root) return

    positioned.set(root.id, {
      ...root,
      x: cx,
      y: cy,
      size: getSemanticNodeSize(root),
      depth: 0,
      clusterId: root.id,
    })

    const firstLevel = cluster.members.filter((member) => member.depth === 1)
    firstLevel.forEach((member, childIndex) => {
      const node = nodesById.get(member.id)
      if (!node) return
      const childAngle = (childIndex / Math.max(1, firstLevel.length)) * Math.PI * 2 - Math.PI / 2
      const radius = CHILD_RING_BASE + Math.min(70, firstLevel.length * 5)
      const x = cx + Math.cos(childAngle) * radius
      const y = cy + Math.sin(childAngle) * radius
      positioned.set(node.id, {
        ...node,
        x,
        y,
        size: getSemanticNodeSize(node),
        depth: 1,
        clusterId: root.id,
      })

      const grandchildren = cluster.members.filter((item) => item.parentId === node.id)
      grandchildren.forEach((grandchild, grandchildIndex) => {
        const grandchildNode = nodesById.get(grandchild.id)
        if (!grandchildNode) return
        const spread = Math.PI * 0.86
        const start = childAngle - spread / 2
        const grandchildAngle = start + (spread * (grandchildIndex + 1)) / (grandchildren.length + 1)
        const grandchildRadius = GRANDCHILD_RING_BASE + Math.min(40, grandchildren.length * 5)
        const gx = x + Math.cos(grandchildAngle) * grandchildRadius
        const gy = y + Math.sin(grandchildAngle) * grandchildRadius
        positioned.set(grandchildNode.id, {
          ...grandchildNode,
          x: gx,
          y: gy,
          size: getSemanticNodeSize(grandchildNode),
          depth: grandchild.depth,
          clusterId: root.id,
        })
      })
    })
  })

  const orphanEntries = [...orphanGroups.entries()]
  const orphanCount = Math.max(1, orphanEntries.length)
  orphanEntries.forEach(([groupId, ids], groupIndex) => {
    const groupAngle = (groupIndex / orphanCount) * Math.PI * 2 + Math.PI / 7
    const groupCx = Math.cos(groupAngle) * ORPHAN_RING_RADIUS
    const groupCy = Math.sin(groupAngle) * ORPHAN_RING_RADIUS * 0.68
    ids.forEach((id, index) => {
      const node = nodesById.get(id)
      if (!node) return
      const jitterSeed = hashString(id)
      const angle = (index / Math.max(1, ids.length)) * Math.PI * 2 + (jitterSeed % 31) / 100
      const radius = 30 + Math.floor(index / 9) * 34 + (jitterSeed % 17)
      const x = groupCx + Math.cos(angle) * radius
      const y = groupCy + Math.sin(angle) * radius
      positioned.set(id, {
        ...node,
        x,
        y,
        size: getSemanticNodeSize(node),
        depth: 3,
        clusterId: groupId,
      })
    })
  })

  return nodes.map((node) => positioned.get(node.id) ?? node)
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
    const visibleLinks = selectVisibleLinks(nodes, edges)
    const layoutNodes = computeHierarchyLayout(nodes, visibleLinks)
    return { nodes: layoutNodes, links: visibleLinks }
  }, [nodes, edges])

  useEffect(() => {
    const graph = graphRef?.current
    if (!graph) return

    const linkForce = graph.d3Force('link') as D3LinkForce | undefined
    linkForce
      ?.distance?.((link) => getWeightedLinkDistance(link))
      ?.strength?.((link) => getWeightedLinkStrength(link))
      ?.iterations?.(2)

    const chargeForce = graph.d3Force('charge') as D3ChargeForce | undefined
    chargeForce
      ?.strength?.((node) => getNodeRepelStrength(node))
      ?.distanceMin?.(36)
      ?.distanceMax?.(780)
      ?.theta?.(0.82)

    const centerForce = graph.d3Force('center') as D3CenterForce | undefined
    centerForce?.strength?.(0.055)

    graph.d3ReheatSimulation()
  }, [graphData, graphRef])

  const getNodeOpacity = useCallback(
    (visualStrength: number) => {
      if (!searchTerm) return 0.82
      if (visualStrength <= 0) return 0.1
      return 0.16 + visualStrength * 0.66
    },
    [searchTerm],
  )

  const getGlowRadius = useCallback((baseRadius: number, visualStrength: number, globalScale: number) => {
    return baseRadius * ((3 + visualStrength * 8) * Math.pow(globalScale, -0.24))
  }, [])

  const drawNode = useCallback((node: NodeObject<GraphNode>, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const strength = getMatchStrength(node)
    const visualStrength = searchTerm ? getVisualMatchStrength(strength) : 0.72
    const matched = visualStrength > 0
    // 검색 점수는 soft-knee 곡선으로 시각화한다. 낮은 유사도도 완전히
    // 사라지지는 않지만, 상위 결과와 같은 halo 체급으로 보이지 않게 한다.
    const opacity = getNodeOpacity(visualStrength)
    const color = NODE_COLOR[node.category] ?? '#81ecff'
    const baseR = ((NODE_DOT_SIZE[node.size] ?? 5) + Math.max(0, 2 - Number(node.depth ?? 2))) / globalScale

    if (matched) {
      ctx.save()

      const glowRadius = getGlowRadius(baseR, visualStrength, globalScale)

      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, glowRadius,
      )

      gradient.addColorStop(0, `rgba(255, 255, 255, ${0.1 + visualStrength * 0.38})`)
      gradient.addColorStop(0.14, `rgba(241, 247, 255, ${0.08 + visualStrength * 0.24})`)
      gradient.addColorStop(0.34, `rgba(116, 195, 213, ${0.025 + visualStrength * 0.1})`)
      gradient.addColorStop(0.68, `rgba(116, 195, 213, ${0.005 + visualStrength * 0.026})`)
      gradient.addColorStop(1, 'rgba(116, 195, 213, 0)')

      ctx.beginPath()
      ctx.arc(node.x, node.y, glowRadius, 0, 2 * Math.PI, false)
      ctx.fillStyle = gradient
      ctx.globalAlpha = opacity
      ctx.fill()

      ctx.beginPath()
      ctx.arc(node.x, node.y, baseR + visualStrength * (0.9 / globalScale), 0, 2 * Math.PI, false)
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
      const fontSize = (node.size === 'root' ? 12 : node.size === 'primary' ? 10 : 8) / globalScale
      ctx.font = `${node.size === 'root' ? '650' : node.size === 'primary' ? '520' : '400'} ${fontSize}px Inter`
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = !matched
        ? (node.size === 'secondary' ? '#707982' : '#adb8c2')
        : visualStrength > 0.45
          ? '#f9f9fd'
          : 'rgba(210, 224, 232, 0.72)'
      ctx.fillText(node.label, node.x + baseR + 8 / globalScale, node.y)
    }

    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
  }, [getGlowRadius, getMatchStrength, getNodeOpacity, searchTerm])

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
            'radial-gradient(ellipse 58% 58% at 50% 50%, rgba(18,22,25,0.48) 0%, transparent 100%)',
        }}
      />

      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeCanvasObject={drawNode}
        nodeLabel="label"
        linkColor={(link) => {
          const typedLink = link as { weight?: number; type?: GraphEdgeType }
          const weight = clamp01(Number(typedLink.weight ?? 0))
          const tension = smoothstep(Math.max(0, weight - 0.52) / 0.48)
          if (typedLink.type === 'parent_of') {
            return `rgba(212,224,238,${0.18 + tension * 0.40})`
          }
          return `rgba(132,216,236,${0.055 + tension * 0.22})`
        }}
        linkWidth={(link) => {
          const typedLink = link as { weight?: number; type?: GraphEdgeType }
          const weight = clamp01(Number(typedLink.weight ?? 0))
          const tension = smoothstep(Math.max(0, weight - 0.52) / 0.48)
          return typedLink.type === 'parent_of' ? 1.1 + tension * 2.3 : 0.52 + tension * 1
        }}
        linkLineDash={(link) => ((link as { type?: GraphEdgeType }).type === 'parent_of' ? [] : [4, 6])}
        backgroundColor="transparent"
        onNodeClick={(node: NodeObject<GraphNode>) => {
          router.push(`/analysis/${node.id}`)
        }}
        onNodeDragEnd={(node: NodeObject<GraphNode>) => {
          node.fx = undefined
          node.fy = undefined
          graphRef?.current?.d3ReheatSimulation()
        }}
        warmupTicks={60}
        cooldownTicks={260}
        d3AlphaDecay={0.026}
        d3VelocityDecay={0.42}
      />
    </div>
  )
}
