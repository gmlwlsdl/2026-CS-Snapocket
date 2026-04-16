"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { CategoryFilter, GraphNode, GraphEdge } from "../knowledgeGraph.type";
import { getNodes, getGraphSummary, type GraphSummaryData } from "@/entities/graph";
import { searchDocuments } from "@/entities/search";
import { CATEGORY_TO_NODE_CATEGORY } from "../knowledgeGraph.utils";
import dynamic from "next/dynamic";
import { SidebarNav, ToastStatus, type ToastItem } from "@/shared/ui";
import { UploadModal } from "@/features/upload";
import { TopHeader } from "./topHeader";
import type { ForceGraphMethods, NodeObject } from "react-force-graph-2d";

const KnowledgeGraphCanvas = dynamic(
  () => import("./knowledgeGraphCanvas").then((mod) => mod.KnowledgeGraphCanvas),
  { ssr: false }
);

import { GraphControls } from "./graphControls";
import { AiInputBar } from "./aiInputBar";

export function KnowledgeGraphPage() {
  const router = useRouter();
  const [activeFilter, setActiveFilter] = useState<CategoryFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [matchedNodeIds, setMatchedNodeIds] = useState<string[] | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [toastItems, setToastItems] = useState<ToastItem[]>([]);
  const [summaryData, setSummaryData] = useState<GraphSummaryData>();

  const graphRef = useRef<ForceGraphMethods<NodeObject<GraphNode>> | undefined>(undefined);

  const handleZoomIn = useCallback(() => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom * 1.2, 400);
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom * 0.8, 400);
    }
  }, []);

  const handleFit = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(600, 80);
    }
  }, []);

  // summary는 카테고리 필터와 무관하므로 마운트 시 1회만 호출
  useEffect(() => {
    getGraphSummary()
      .then(setSummaryData)
      .catch((err) => console.error("Failed to load graph summary:", err));
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadNodes() {
      const categoryMap: Record<CategoryFilter, string | undefined> = {
        all: undefined,
        lecture: "lecture",
        assignment: "assignment",
        notice: "notice",
        receipt: "receipt",
        memo: "memo",
      };

      try {
        const apiNodes = await getNodes(categoryMap[activeFilter]);

        if (!controller.signal.aborted) {
          const mappedNodes: GraphNode[] = apiNodes.map((n) => ({
            id: n.id,
            label: n.title,
            x: 0,
            y: 0,
            category: CATEGORY_TO_NODE_CATEGORY[n.category] ?? "misc",
            size: n.connectionCount > 2 ? "primary" : "secondary",
          }));

          setNodes(mappedNodes);

          // [FE_MOCK] 백엔드 엣지 API 연동 전 임시로 노드를 순차 연결하여 시각화
          if (mappedNodes.length > 1) {
            const mockEdges: GraphEdge[] = mappedNodes.slice(0, -1).map((n, i) => ({
              from: n.id,
              to: mappedNodes[i + 1].id,
            }));
            setEdges(mockEdges);
          } else {
            setEdges([]);
          }
        }
      } catch (error) {
        console.error("Failed to load graph data:", error);
      }
    }

    loadNodes();

    return () => controller.abort();
  }, [activeFilter]);

  useEffect(() => {
    const controller = new AbortController();
    const keyword = searchTerm.trim();

    async function loadMatches() {
      if (!keyword) {
        setMatchedNodeIds(null);
        return;
      }

      const categoryMap: Record<CategoryFilter, string | undefined> = {
        all: undefined,
        lecture: "lecture",
        assignment: "assignment",
        notice: "notice",
        receipt: "receipt",
        memo: "memo",
      };

      try {
        const searchItems = await searchDocuments({
          keyword,
          category: categoryMap[activeFilter],
          page: 1,
          size: 100,
        });

        if (!controller.signal.aborted) {
          setMatchedNodeIds(searchItems.map((item) => item.id));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error("Failed to load search matches:", error);
          setMatchedNodeIds([]);
        }
      }
    }

    loadMatches();
    return () => controller.abort();
  }, [activeFilter, searchTerm]);

  const handleUpload = useCallback(async (file: File) => {
    const { uploadDocument } = await import("@/entities/document");

    try {
      const uploadRes = await uploadDocument(file);
      const documentId = uploadRes.document_id;

      setToastItems((prev) => [
        { id: documentId, fileName: file.name, status: "processing", analysisId: documentId },
        ...prev,
      ]);
    } catch (error) {
      console.error("Upload failed:", error);
    }
  }, []);

  const handleToastClick = useCallback(
    (item: ToastItem) => {
      if (item.status === "complete") {
        router.push(`/analysis/${item.analysisId}?mode=result`);
      }
    },
    [router]
  );

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
        <AiInputBar onSearch={setSearchTerm} />
        <ToastStatus items={toastItems} onItemClick={handleToastClick} />
      </main>

      <UploadModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onUpload={handleUpload}
      />
    </div>
  );
}
