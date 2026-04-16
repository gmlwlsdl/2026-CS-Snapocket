import React, { useCallback, useMemo, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import type { CategoryFilter, GraphNode, GraphEdge } from "../knowledgeGraph.type";
import {
  NODE_COLOR,
  NODE_DOT_SIZE,
} from "../knowledgeGraph.constant";

interface KnowledgeGraphCanvasProps {
  activeFilter: CategoryFilter;
  searchTerm?: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  graphRef?: React.MutableRefObject<ForceGraphMethods | undefined>;
}

export function KnowledgeGraphCanvas({
  activeFilter,
  searchTerm,
  nodes,
  edges,
  graphRef,
}: KnowledgeGraphCanvasProps) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);

  // 검색어 매칭 여부 확인 유틸
  const isMatched = useCallback((label: string) => {
    if (!searchTerm) return true;
    return label.toLowerCase().includes(searchTerm.toLowerCase());
  }, [searchTerm]);

  const isCategoryMatch = useCallback((node: GraphNode) => {
    if (activeFilter === "all") return true;
    // 백엔드 단수형 명칭에 맞게 매칭 (동적 대응을 위해 CategoryFilter와 node.category를 직접 비교)
    return node.category === activeFilter;
  }, [activeFilter]);

  // 그래프 데이터 가공
  const graphData = useMemo(() => {
    const filteredNodes = nodes.filter(isCategoryMatch);
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    
    const filteredLinks = edges
      .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
      .map(e => ({
        source: e.from,
        target: e.to,
      }));

    return {
      nodes: filteredNodes.map(n => ({
        ...n,
        // react-force-graph expects id
        id: n.id,
      })),
      links: filteredLinks,
    };
  }, [nodes, edges, isCategoryMatch]);

  // 화면 크기에 맞게 그래프 조정
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && graphRef?.current) {
        const { clientWidth, clientHeight } = containerRef.current;
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // 커스텀 노드 렌더링 (Star Effect - Radial Gradient)
  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const matched = isMatched(node.label);
    const opacity = matched ? 1 : 0.1;
    const color = NODE_COLOR[node.category] ?? "#81ecff";
    const baseR = (NODE_DOT_SIZE[node.size] ?? 5) / globalScale;

    if (matched) {
      ctx.save();
      
      // 광원 범위 설정 (줌 레벨에 따라 광학적으로 자연스러운 감쇄 적용)
      // 멀리서 볼 때(줌 아웃) 광원이 너무 커 보이지 않도록 globalScale의 영향을 비선형적으로 조절
      const glowRadius = baseR * (10 * Math.pow(globalScale, -0.3));

      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, glowRadius
      );
      
      // 자연스러운 별빛 컬러 스탑 (중심은 핵처럼 밝고 외곽은 부드럽게 감쇄)
      gradient.addColorStop(0, "rgba(255, 255, 255, 1)");  // 중심부 하얀 핵
      gradient.addColorStop(0.1, "rgba(129, 236, 255, 0.9)"); // Snap Blue 코어
      gradient.addColorStop(0.3, "rgba(129, 236, 255, 0.3)"); // 중간층 번짐
      gradient.addColorStop(0.6, "rgba(129, 236, 255, 0.05)"); // 외곽부 미세 광원
      gradient.addColorStop(1, "rgba(129, 236, 255, 0)");   // 배경과 완벽히 동화

      ctx.beginPath();
      ctx.arc(node.x, node.y, glowRadius, 0, 2 * Math.PI, false);
      ctx.fillStyle = gradient;
      ctx.globalAlpha = opacity;
      ctx.fill();
      
      ctx.restore();
    } else {
      // 매칭되지 않은 노드는 단순한 점으로 표현
      ctx.beginPath();
      ctx.arc(node.x, node.y, baseR, 0, 2 * Math.PI, false);
      ctx.fillStyle = color;
      ctx.globalAlpha = opacity;
      ctx.fill();
    }

    // 레이블 렌더링 (모든 노드 타이틀 상시 표시)
    if (globalScale > 0.8) {
      const fontSize = (node.size === "primary" ? 11 : 9) / globalScale;
      ctx.font = `${node.size === "primary" ? "500" : "400"} ${fontSize}px Inter`;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillStyle = matched ? "#f9f9fd" : "#aaabaf"; // 매칭 여부에 따라 색상 차이만 부여
      ctx.fillText(node.label, node.x + baseR + 8 / globalScale, node.y);
    }

    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;
  }, [isMatched]);

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden flex items-center justify-center"
      style={{ background: "#0c0e11" }}
    >
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 60% at 50% 50%, rgba(23,26,29,0.8) 0%, transparent 100%)",
        }}
      />
      
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeCanvasObject={drawNode}
        nodeLabel="label"
        itemColor={node => NODE_COLOR[(node as any).category]}
        linkColor={() => "rgba(129,236,255,0.12)"}
        linkWidth={1}
        backgroundColor="transparent"
        onNodeClick={(node: any) => {
          router.push(`/analysis/${node.id}`);
        }}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
