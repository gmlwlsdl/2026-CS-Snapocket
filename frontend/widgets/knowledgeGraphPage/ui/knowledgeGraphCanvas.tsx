import React, { useCallback, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from 'react-force-graph-2d'
import type { GraphNode, GraphEdge, GraphEdgeType } from '../knowledgeGraph.type'
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

const ORPHAN_RING_RADIUS = 420
const CLUSTER_RING_RADIUS = 280
const CHILD_RING_BASE = 74
const GRANDCHILD_RING_BASE = 48

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value))
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

  const parentIncidentIds = new Set<string>()
  parentLinks.forEach((edge) => {
    parentIncidentIds.add(edge.source)
    parentIncidentIds.add(edge.target)
  })

  const similarUseCount = new Map<string, number>()
  const sparseSimilarLinks = validEdges
    .filter((edge) => edge.type === 'similar_to' && edge.weight >= 0.72)
    .sort((a, b) => b.weight - a.weight)
    .filter((edge) => {
      // Similarity links are useful inside otherwise orphaned islands, but they
      // should not bridge semantic branches into a hairball.
      if (parentIncidentIds.has(edge.from) || parentIncidentIds.has(edge.to)) {
        return false
      }
      const fromCount = similarUseCount.get(edge.from) ?? 0
      const toCount = similarUseCount.get(edge.to) ?? 0
      if (fromCount >= 1 || toCount >= 1) return false
      similarUseCount.set(edge.from, fromCount + 1)
      similarUseCount.set(edge.to, toCount + 1)
      return true
    })
    .map((edge) => ({
      source: edge.from,
      target: edge.to,
      weight: edge.weight,
      type: edge.type,
    }))

  return [...parentLinks, ...sparseSimilarLinks]
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
      fx: cx,
      fy: cy,
      size: 'root',
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
        fx: x,
        fy: y,
        size: 'primary',
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
          fx: gx,
          fy: gy,
          size: 'secondary',
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
        fx: x,
        fy: y,
        size: 'secondary',
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
    const baseR = ((NODE_DOT_SIZE[node.size] ?? 5) + Math.max(0, 2 - Number(node.depth ?? 2))) / globalScale

    if (matched) {
      ctx.save()

      const glowRadius = getGlowRadius(baseR, normalizedStrength, globalScale)

      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, glowRadius,
      )

      gradient.addColorStop(0, 'rgba(255, 255, 255, 1)')
      gradient.addColorStop(0.12, `rgba(241, 247, 255, ${0.45 + normalizedStrength * 0.35})`)
      gradient.addColorStop(0.3, `rgba(116, 195, 213, ${0.16 + normalizedStrength * 0.14})`)
      gradient.addColorStop(0.6, `rgba(116, 195, 213, ${0.03 + normalizedStrength * 0.04})`)
      gradient.addColorStop(1, 'rgba(116, 195, 213, 0)')

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
      const fontSize = (node.size === 'root' ? 12 : node.size === 'primary' ? 10 : 8) / globalScale
      ctx.font = `${node.size === 'root' ? '650' : node.size === 'primary' ? '520' : '400'} ${fontSize}px Inter`
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = matched ? '#f9f9fd' : node.size === 'secondary' ? '#707982' : '#adb8c2'
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
        linkColor={(link) => {
          const typedLink = link as { weight?: number; type?: GraphEdgeType }
          const weight = clamp01(Number(typedLink.weight ?? 0))
          if (typedLink.type === 'parent_of') {
            return `rgba(198,208,222,${0.24 + weight * 0.34})`
          }
          return `rgba(116,195,213,${0.05 + weight * 0.1})`
        }}
        linkWidth={(link) => {
          const typedLink = link as { weight?: number; type?: GraphEdgeType }
          const weight = clamp01(Number(typedLink.weight ?? 0))
          return typedLink.type === 'parent_of' ? 1.4 + weight * 2.4 : 0.5 + weight * 0.8
        }}
        linkLineDash={(link) => ((link as { type?: GraphEdgeType }).type === 'similar_to' ? [4, 6] : [])}
        backgroundColor="transparent"
        onNodeClick={(node: NodeObject<GraphNode>) => {
          router.push(`/analysis/${node.id}`)
        }}
        cooldownTicks={1}
        d3AlphaDecay={0.4}
        d3VelocityDecay={0.8}
      />
    </div>
  )
}
