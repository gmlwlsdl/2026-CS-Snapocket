import type { CategoryFilter, GraphNode, GraphEdge } from "../knowledgeGraph.type";
import {
  CANVAS_WIDTH,
  CANVAS_HEIGHT,
  NODE_COLOR,
  NODE_DOT_SIZE,
  NODE_DOT_OPACITY,
} from "../knowledgeGraph.constant";

const PRIMARY_LABEL_STYLE = { color: "#f9f9fd", fontSize: 12, fontWeight: 400 } as const;
const SECONDARY_LABEL_STYLE = { color: "#aaabaf", fontSize: 10, fontWeight: 400 } as const;

function isNodeVisible(node: GraphNode, filter: CategoryFilter): boolean {
  if (filter === "all") return true;
  if (filter === "assignments") return node.category === "assignment";
  if (filter === "exams") return node.category === "exam";
  if (filter === "class-materials") return node.category === "class";
  if (filter === "summaries") return node.category === "summary";
  return true;
}

interface KnowledgeGraphCanvasProps {
  activeFilter: CategoryFilter;
  searchTerm?: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function KnowledgeGraphCanvas({
  activeFilter,
  searchTerm,
  nodes,
  edges,
}: KnowledgeGraphCanvasProps) {
  const visibleNodes = nodes.filter((n) => isNodeVisible(n, activeFilter));
  const visibleIds = new Set(visibleNodes.map((n) => n.id));
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  // 검색어 필터링 유틸
  const isMatched = (label: string) => {
    if (!searchTerm) return true;
    return label.toLowerCase().includes(searchTerm.toLowerCase());
  };

  return (
    <div
      className="relative h-full w-full overflow-hidden"
      style={{ background: "#0c0e11" }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 60% at 50% 50%, rgba(23,26,29,0.8) 0%, transparent 100%)",
        }}
      />

      <svg
        viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        {edges.map((edge) => {
          if (!visibleIds.has(edge.from) || !visibleIds.has(edge.to)) return null;
          const from = nodeMap.get(edge.from);
          const to = nodeMap.get(edge.to);
          if (!from || !to) return null;

          // 두 노드 중 하나라도 검색어와 매칭되지 않으면 간선을 투명하게 처리 (맥락 유지 위해 0.05)
          const edgeOpacity = isMatched(from.label) && isMatched(to.label) ? 1 : 0.05;

          return (
            <line
              key={`${edge.from}-${edge.to}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="rgba(129,236,255,0.12)"
              strokeWidth="1"
              opacity={edgeOpacity}
              style={{ transition: "opacity 0.3s" }}
            />
          );
        })}

        {visibleNodes.map((node) => {
          const color = NODE_COLOR[node.category] ?? "#aaabaf";
          const dotSize = NODE_DOT_SIZE[node.size] ?? 8;
          const baseOpacity = NODE_DOT_OPACITY[node.size] ?? 0.6;

          // 검색어 매칭 여부에 따른 투명도 조절
          const matched = isMatched(node.label);
          const finalOpacity = matched ? baseOpacity : 0.05;

          return (
            <circle
              key={node.id}
              cx={node.x}
              cy={node.y}
              r={dotSize / 2}
              fill={color}
              opacity={finalOpacity}
              style={{ transition: "opacity 0.3s" }}
            />
          );
        })}
      </svg>

      <div className="absolute inset-0" aria-label="Knowledge graph nodes">
        {visibleNodes.map((node) => {
          const xPct = (node.x / CANVAS_WIDTH) * 100;
          const yPct = (node.y / CANVAS_HEIGHT) * 100;
          const dotSize = NODE_DOT_SIZE[node.size] ?? 8;

          const matched = isMatched(node.label);
          const labelOpacity = matched ? 1 : 0.05;

          return (
            <div
              key={node.id}
              className="absolute flex items-center gap-2"
              style={{
                left: `${xPct}%`,
                top: `${yPct}%`,
                transform: "translate(0, -50%)",
                opacity: labelOpacity,
                transition: "opacity 0.3s",
              }}
            >
              <div style={{ width: dotSize, height: dotSize, flexShrink: 0 }} />
              <span
                className="whitespace-nowrap font-inter leading-none"
                style={node.size === "primary" ? PRIMARY_LABEL_STYLE : SECONDARY_LABEL_STYLE}
              >
                {node.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
