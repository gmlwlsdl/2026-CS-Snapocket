"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { CategoryFilter, GraphNode, GraphEdge, GraphSummaryData } from "../knowledgeGraph.type";
import { GRAPH_NODES, GRAPH_EDGES } from "../knowledgeGraph.constant";
import { getNodes, getGraphSummary } from "@/entities/graph";
import { CATEGORY_TO_NODE_CATEGORY } from "../knowledgeGraph.utils";
import dynamic from "next/dynamic";
import { SidebarNav, ToastStatus, type ToastItem } from "@/shared/ui";
import { UploadModal } from "@/features/upload";
import { TopHeader } from "./topHeader";
import type { ForceGraphMethods } from "react-force-graph-2d";

const KnowledgeGraphCanvas = dynamic(
  () => import("./knowledgeGraphCanvas").then((mod) => mod.KnowledgeGraphCanvas),
  { ssr: false }
);

import { GraphControls } from "./graphControls";
import { AiInputBar } from "./aiInputBar";

// [API_ANNOTATED] Mock 토스트 데이터 주석 처리
/*
const INITIAL_TOASTS: ToastItem[] = [
  {
    id: "mock-1",
    fileName: "CS204_Lecture_Notes.pdf",
    status: "complete",
    analysisId: "mock-1",
  },
  {
    id: "mock-2",
    fileName: "Algorithm_Assignment3.pdf",
    status: "processing",
    analysisId: "mock-2",
  },
];
*/
const INITIAL_TOASTS: ToastItem[] = [];


export function KnowledgeGraphPage() {
  const router = useRouter();
  const [activeFilter, setActiveFilter] = useState<CategoryFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [toastItems, setToastItems] = useState<ToastItem[]>(INITIAL_TOASTS);
  const [summaryData, setSummaryData] = useState<GraphSummaryData>();

  const nextIdRef = useRef(100);
  const processingTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const graphRef = useRef<ForceGraphMethods>();

  // 그래프 제어 핸들러
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

  useEffect(() => {
    const controller = new AbortController();

    async function loadData() {
      try {
        // CategoryFilter -> ApiNodeCategory 맵핑
        const categoryMap: Record<CategoryFilter, any> = {
          all: undefined,
          lecture: "lecture",
          assignment: "assignment",
          notice: "notice",
          receipt: "receipt",
          memo: "memo",
        };

        const [apiNodes, summary] = await Promise.all([
          getNodes(categoryMap[activeFilter]),
          getGraphSummary(),
        ]);

        if (!controller.signal.aborted) {
          // react-force-graph가 좌표를 자동 계산하므로 raw nodes를 그대로 매핑
          const mappedNodes: GraphNode[] = apiNodes.map((n) => ({
            id: n.id,
            label: n.title,
            x: 0,
            y: 0,
            category: CATEGORY_TO_NODE_CATEGORY[n.category] ?? "misc",
            size: n.connectionCount > 2 ? "primary" : "secondary",
          }));
          
          setNodes(mappedNodes);
          setSummaryData(summary);
          
          // [FE_MOCK] 백엔드 엣지가 없을 경우 노드들을 서로 연결하여 시각화 (임시)
          if (mappedNodes.length > 1) {
            const mockEdges: GraphEdge[] = [];
            for (let i = 0; i < mappedNodes.length - 1; i++) {
              mockEdges.push({
                from: mappedNodes[i].id,
                to: mappedNodes[i + 1].id,
              });
            }
            setEdges(mockEdges);
          } else {
            setEdges([]);
          }
        }
      } catch (error) {
        console.error("Failed to load graph data:", error);
      }
    }

    loadData();

    return () => controller.abort();
  }, [activeFilter]);



  // [API_ANNOTATED] Mock 토스트 업데이트 로직 제거
  /*
  useEffect(() => {
    const timer = setTimeout(() => {
      setToastItems((prev) =>
        prev.map((item) =>
          item.id === "mock-2" ? { ...item, status: "complete" } : item
        )
      );
    }, 3500);
    return () => clearTimeout(timer);
  }, []);
  */


  // [API_ANNOTATED] 실제 업로드 API 호출 연동
  const handleUpload = useCallback(async (file: File) => {
    const { uploadDocument } = await import("@/entities/document");
    
    try {
      const uploadRes = await uploadDocument(file);
      const documentId = uploadRes.document_id;

      const newItem: ToastItem = {
        id: documentId,
        fileName: file.name,
        status: "processing",
        analysisId: documentId,
      };

      setToastItems((prev) => [newItem, ...prev]);

      // TODO: 이후 fetchAnalysisStatus 폴링 로직 추가 가능
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

  useEffect(() => {
    const timers = processingTimersRef.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
      timers.clear();
    };
  }, []);

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
            activeFilter={activeFilter}
            searchTerm={searchTerm}
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
