import React, { useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "../knowledgeGraph.type";
import {
  NODE_COLOR,
  NODE_DOT_SIZE,
} from "../knowledgeGraph.constant";

interface KnowledgeGraphCanvasProps {
  searchTerm?: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  graphRef?: React.MutableRefObject<ForceGraphMethods | undefined>;
}

export function KnowledgeGraphCanvas({
  searchTerm,
  nodes,
  edges,
  graphRef,
}: KnowledgeGraphCanvasProps) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);

  const isMatched = useCallback((label: string) => {
    if (!searchTerm) return true;
    return label.toLowerCase().includes(searchTerm.toLowerCase());
  }, [searchTerm]);

  const graphData = useMemo(() => {
    const nodeIds = new Set(nodes.map(n => n.id));

    const filteredLinks = edges
      .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
      .map(e => ({
        source: e.from,
        target: e.to,
      }));

    return { nodes, links: filteredLinks };
  }, [nodes, edges]);

  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const matched = isMatched(node.label);
    const opacity = matched ? 1 : 0.1;
    const color = NODE_COLOR[node.category] ?? "#81ecff";
    const baseR = (NODE_DOT_SIZE[node.size] ?? 5) / globalScale;

    if (matched) {
      ctx.save();

      // 줌 아웃 시 광원이 과도하게 커지지 않도록 globalScale의 영향을 비선형적으로 감쇄
      const glowRadius = baseR * (10 * Math.pow(globalScale, -0.3));

      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, glowRadius
      );

      gradient.addColorStop(0, "rgba(255, 255, 255, 1)");
      gradient.addColorStop(0.1, "rgba(129, 236, 255, 0.9)");
      gradient.addColorStop(0.3, "rgba(129, 236, 255, 0.3)");
      gradient.addColorStop(0.6, "rgba(129, 236, 255, 0.05)");
      gradient.addColorStop(1, "rgba(129, 236, 255, 0)");

      ctx.beginPath();
      ctx.arc(node.x, node.y, glowRadius, 0, 2 * Math.PI, false);
      ctx.fillStyle = gradient;
      ctx.globalAlpha = opacity;
      ctx.fill();

      ctx.restore();
    } else {
      ctx.beginPath();
      ctx.arc(node.x, node.y, baseR, 0, 2 * Math.PI, false);
      ctx.fillStyle = color;
      ctx.globalAlpha = opacity;
      ctx.fill();
    }

    if (globalScale > 0.8) {
      const fontSize = (node.size === "primary" ? 11 : 9) / globalScale;
      ctx.font = `${node.size === "primary" ? "500" : "400"} ${fontSize}px Inter`;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillStyle = matched ? "#f9f9fd" : "#aaabaf";
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
