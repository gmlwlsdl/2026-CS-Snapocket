"use client";

import type { CategoryFilter } from "../knowledgeGraph.type";
import type { GraphSummaryData } from "@/entities/graph";
import { CATEGORY_FILTERS } from "../knowledgeGraph.constant";
import { ThemeToggle } from "@/shared/ui";

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
      style={{
        background: "var(--th-header-bg)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--th-separator)",
      }}
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

      {/* 카테고리 칩 */}
      <nav className="flex items-center gap-2" aria-label="Category filters">
        {CATEGORY_FILTERS.map(({ id, label }) => {
          const isActive = activeFilter === id;
          return (
            <button
              key={id}
              onClick={() => onFilterChange(id)}
              className="flex items-center px-4 h-[28px] rounded-full font-manrope transition-colors cursor-pointer"
              style={
                isActive
                  ? {
                      background: "var(--th-chip-active-bg)",
                      color: "var(--th-chip-active-text)",
                      fontSize: 12,
                      fontWeight: 500,
                      letterSpacing: -0.4,
                    }
                  : {
                      background: "var(--th-chip-inactive-bg)",
                      border: "1px solid var(--th-chip-inactive-border)",
                      color: "var(--th-chip-inactive-text)",
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
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Nodes
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {summaryData?.node_count ?? 0}
          </span>
        </div>
        <div
          className="flex flex-col items-end pl-6"
          style={{ borderLeft: "1px solid var(--th-border)" }}
        >
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Docs
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {documentCount}
          </span>
        </div>
        <div
          className="flex flex-col items-end pl-6"
          style={{ borderLeft: "1px solid var(--th-border)" }}
        >
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Tags
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {summaryData?.tag_count ?? 0}
          </span>
        </div>
        <div
          className="flex flex-col items-end pl-6"
          style={{ borderLeft: "1px solid var(--th-border)" }}
        >
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Edges
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {summaryData?.edge_count ?? 0}
          </span>
        </div>

        <div className="pl-4" style={{ borderLeft: "1px solid var(--th-border)" }}>
          <ThemeToggle />
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
            display: none !important;
          }
        }
      `}</style>
    </header>
  );
}
