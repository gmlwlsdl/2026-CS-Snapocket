"use client";

import type { CategoryFilter } from "../knowledgeGraph.type";
import type { GraphSummaryData } from "@/entities/graph";
import { CATEGORY_FILTERS } from "../knowledgeGraph.constant";

interface TopHeaderProps {
  activeFilter: CategoryFilter;
  onFilterChange: (filter: CategoryFilter) => void;
  summaryData?: GraphSummaryData;
}

export function TopHeader({ activeFilter, onFilterChange, summaryData }: TopHeaderProps) {
  const documentCount = summaryData?.document_count ?? summaryData?.documents_count ?? 0;

  return (
    <header
      className="fixed left-[81px] right-0 top-0 z-10 flex h-16 items-center px-6"
      style={{ background: "rgba(12,14,17,0.7)", backdropFilter: "blur(12px)" }}
    >
      {/* 브랜드명 */}
      <div className="mr-8">
        <span
          className="font-manrope font-bold"
          style={{
            fontSize: 20,
            letterSpacing: -0.4,
            lineHeight: "28px",
            background: "linear-gradient(90deg, #81ecff 0%, #ac89ff 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          Snapocket
        </span>
      </div>

      {/* TODO: [API] getGraphSummary() 결과(node_count, tag_count)를 헤더 우측에 표시 */}
      {/* TODO: [API] 카테고리 필터 변경 시 부모(KnowledgeGraphPage)의 getNodes(category) 재호출이 이루어지도록
            현재 onFilterChange prop이 상위에서 처리 중이므로 상위 useEffect에 activeFilter 의존성 추가 필요 */}
      {/* 카테고리 칩 */}
      <nav className="flex items-center gap-2" aria-label="Category filters">
        {CATEGORY_FILTERS.map(({ id, label }) => {
          const isActive = activeFilter === id;
          return (
            <button
              key={id}
              onClick={() => onFilterChange(id)}
              className="flex items-center px-4 h-[28px] rounded-full font-manrope transition-colors"
              style={
                isActive
                  ? {
                      background: "#81ecff",
                      color: "#003840",
                      fontSize: 12,
                      fontWeight: 500,
                      letterSpacing: -0.4,
                    }
                  : {
                      background: "#111417",
                      border: "1px solid rgba(70,72,75,0.15)",
                      color: "#aaabaf",
                      fontSize: 12,
                      fontWeight: 500,
                      letterSpacing: -0.4,
                    }
              }
            >
              {label}
            </button>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-6">
        <div className="flex flex-col items-end">
          <span className="text-[10px] uppercase tracking-[1px] text-snap-muted">Nodes</span>
          <span className="text-[14px] font-bold text-snap-white">
            {summaryData?.node_count ?? 0}
          </span>
        </div>
        <div className="flex flex-col items-end border-l border-snap-border/10 pl-6">
          <span className="text-[10px] uppercase tracking-[1px] text-snap-muted">Docs</span>
          <span className="text-[14px] font-bold text-snap-white">
            {documentCount}
          </span>
        </div>
        <div className="flex flex-col items-end border-l border-snap-border/10 pl-6">
          <span className="text-[10px] uppercase tracking-[1px] text-snap-muted">Tags</span>
          <span className="text-[14px] font-bold text-snap-white">
            {summaryData?.tag_count ?? 0}
          </span>
        </div>
        <div className="flex flex-col items-end border-l border-snap-border/10 pl-6">
          <span className="text-[10px] uppercase tracking-[1px] text-snap-muted">Edges</span>
          <span className="text-[14px] font-bold text-snap-white">
            {summaryData?.edge_count ?? 0}
          </span>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          header {
            left: 0 !important;
            flex-direction: column !important;
            height: auto !important;
            padding: 12px !important;
            gap: 8px !important;
            align-items: stretch !important;
          }
          header > div:first-child {
            display: flex !important;
            justify-content: space-between !important;
            width: 100% !important;
          }
          header nav {
            overflow-x: auto !important;
            white-space: nowrap !important;
            padding-bottom: 4px !important;
            justify-content: flex-start !important;
            width: 100% !important;
            scrollbar-width: none;
          }
          header nav::-webkit-scrollbar {
            display: none;
          }
          header > div:last-child {
            display: none !important; /* 모바일에서 통계 요약은 숨김 처리 */
          }
        }
      `}</style>
    </header>
  );
}
